// SKRATCHA FEED - by JJ DA PLUG
//
// An insert effect that feeds a track (or the master) into SKRATCHA, so the turntables can
// record it (REC / GRAB) or scratch it live.
//
//   input ──► capture ring (shared memory, channel 1..4) ──► SKRATCHA reads it
//     │
//     └──► output: the dry track ── or, while SKRATCHA scratches this channel LIVE and
//                                   "Live Mode" is REPLACE, the scratched track coming back
//                                   from SKRATCHA (return ring), cross-faded in 6 ms.
//
// The link lives in volatile shared memory (tmpfs) and disappears with the last FEED instance or
// a reboot. FEED never writes to the drive. Without SKRATCHA it is a plain pass-through.

#include "mpc_plugin.h"
#include "skr_feed.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <thread>

namespace {

enum ParamIndex
{
    kLevel = 0,      // input trim into SKRATCHA (dB); harmless for the host nudge
    kChannel,        // link channel 1..4 (must match "Quelle" in SKRATCHA)
    kLiveMode,       // REPLACE = while LIVE, the track plays the scratched version; ALWAYS DRY = track stays
    kStatus,         // read only: status text
    kMeter,          // read only: input level
    kNumParams
};

} // namespace

class SkratchaFeed : public mpc::Plugin
{
public:
    SkratchaFeed() : mpc::Plugin(makeInfo())
    {
        auto ro = [](mpc::Param p) { p.automatable = false; return p; };
        addParam(mpc::floatParam("level", "Feed Level", -24.0f, 12.0f, 0.0f, "dB", 1));
        addParam(mpc::choiceParam("channel", "Channel", {"FEED 1", "FEED 2", "FEED 3", "FEED 4"}, 0));
        addParam(mpc::choiceParam("livemode", "Live Mode", {"REPLACE", "ALWAYS DRY"}, 0));
        addParam(ro(mpc::floatParam("status", "Status", 0.0f, 1.0f, 0.0f, "", 2)));
        addParam(ro(mpc::floatParam("meter", "Input", 0.0f, 1.0f, 0.0f, "", 2)));
        addProgram("Feed 1", {0.0f, 0.0f, 0.0f, 0.0f, 0.0f});
        addProgram("Feed 2", {0.0f, 1.0f, 0.0f, 0.0f, 0.0f});
        worker_ = std::thread([this] { workerLoop(); });
    }

    ~SkratchaFeed() override
    {
        stop_.store(true);
        if (worker_.joinable()) worker_.join();
        detach();
    }

    void prepare(double sampleRate, int maxBlockSize) override
    {
        sr_ = sampleRate > 1000.0 ? sampleRate : 44100.0;
        maxBlock_ = std::max(32, maxBlockSize);
        fadeStep_ = 1.0f / (float)(0.006 * sr_);
    }

    void reset() override { mixRet_ = 0.0f; }

    void process(mpc::ProcessContext& ctx) override
    {
        const int n = ctx.numFrames;
        const int nch = std::min(ctx.numOutputs, 2);
        float* oL = ctx.outputs[0];
        float* oR = nch > 1 ? ctx.outputs[1] : nullptr;
        const float* iL = (ctx.inputs != nullptr && ctx.numInputs > 0) ? ctx.inputs[0] : nullptr;
        const float* iR = (ctx.inputs != nullptr && ctx.numInputs > 1) ? ctx.inputs[1] : iL;
        skrfeed::Shared* s = link_.load(std::memory_order_acquire);   // (re)mapped by the worker thread

        if (s == nullptr)
        {
            for (int i = 0; i < n; ++i) { const float l = iL ? iL[i] : 0.0f, r = iR ? iR[i] : 0.0f; oL[i] = l; if (oR) oR[i] = r; }
            return;
        }
        skrfeed::Header& h = s->h;
        const uint32_t lat = (uint32_t)std::min<int>(2 * maxBlock_ + 128, (int)skrfeed::kRetFrames / 2);
        h.latency.store(lat, std::memory_order_relaxed);
        h.sampleRate.store((uint32_t)std::lround(sr_), std::memory_order_relaxed);
        h.replaceMode.store(getInt(kLiveMode) == 0 ? 1u : 0u, std::memory_order_relaxed);

        // 1) capture
        const float trim = std::pow(10.0f, get(kLevel) / 20.0f);
        const uint64_t w0 = h.writePos.load(std::memory_order_relaxed);
        float pk = 0.0f;
        for (int i = 0; i < n; ++i)
        {
            const float l = iL ? iL[i] : 0.0f, r = iR ? iR[i] : 0.0f;
            const uint32_t k = (uint32_t)((w0 + (uint64_t)i) & skrfeed::kCapMask);
            const float cl = san(l * trim), cr = san(r * trim);
            s->cap[2 * k] = cl; s->cap[2 * k + 1] = cr;
            pk = std::max(pk, std::max(std::fabs(cl), std::fabs(cr)));
        }
        h.writePos.store(w0 + (uint64_t)n, std::memory_order_release);
        h.feedAlive.fetch_add(1, std::memory_order_relaxed);
        h.peak.store((uint32_t)std::min(9999.0f, pk * 1000.0f), std::memory_order_relaxed);
        peak_ = std::max(pk, peak_ * 0.9f);

        // 2) is SKRATCHA scratching this channel live right now?
        const uint32_t alive = h.skrAlive.load(std::memory_order_relaxed);
        if (alive != lastSkrAlive_) { lastSkrAlive_ = alive; skrIdle_ = 0; } else if (skrIdle_ < 1000000) skrIdle_ += n;
        const bool skrLive = h.liveOn.load(std::memory_order_relaxed) != 0 && skrIdle_ < (int)(0.08 * sr_);
        const uint64_t rp = h.retPos.load(std::memory_order_acquire);
        const uint64_t readEnd = w0 + (uint64_t)n;                    // timeline of this block's last frame + 1
        const bool haveRet = readEnd > lat && rp >= readEnd - lat && rp - (readEnd - lat) < skrfeed::kRetFrames / 2;
        const bool useRet = getInt(kLiveMode) == 0 && skrLive && haveRet;
        live_ = skrLive;

        // 3) output: dry track or the scratched return, cross-faded
        for (int i = 0; i < n; ++i)
        {
            const float l = iL ? iL[i] : 0.0f, r = iR ? iR[i] : 0.0f;
            if (useRet) mixRet_ = std::min(1.0f, mixRet_ + fadeStep_); else mixRet_ = std::max(0.0f, mixRet_ - fadeStep_);
            float ol = l, orr = r;
            if (mixRet_ > 0.0f)
            {
                float rl = 0.0f, rr = 0.0f;
                const uint64_t t = w0 + (uint64_t)i;
                if (t >= lat && haveRet)
                {
                    const uint32_t k = (uint32_t)((t - lat) & skrfeed::kRetMask);
                    rl = s->ret[2 * k]; rr = s->ret[2 * k + 1];
                }
                ol = l + (rl - l) * mixRet_; orr = r + (rr - r) * mixRet_;
            }
            oL[i] = ol; if (oR) oR[i] = orr;
        }
        if (++uiTick_ >= 16) uiTick_ = 0;
    }

    bool formatValue(int index, float plainValue, std::string& out) override
    {
        (void)plainValue;
        if (index == kStatus)
        {
            if (link_.load() == nullptr) out = "NO LINK";
            else if (live_) out = getInt(kLiveMode) == 0 ? "LIVE: SKRATCHA PLAYS TRACK" : "LIVE (TRACK STAYS DRY)";
            else out = "READY FOR SKRATCHA";
            return true;
        }
        if (index == kMeter) { out = peak_ > 0.0005f ? std::to_string((int)std::lround(20.0f * std::log10(peak_))) + " dB" : "-inf"; return true; }
        return false;
    }

private:
    static float san(float x) { return (std::isfinite(x) && std::fabs(x) < 64.0f) ? x : 0.0f; }

    // worker thread: maps the chosen channel (never on the audio thread) and refreshes the status texts
    void workerLoop()
    {
        int tick = 0;
        while (!stop_.load())
        {
            const int want = mpc::clamp(getInt(kChannel), 0, skrfeed::kChannels - 1);
            if (want != channel_ || (link_.load() == nullptr && tick % 20 == 0))
            {
                skrfeed::Shared* fresh = skrfeed::mapChannel(want, true);
                if (fresh != nullptr) fresh->h.users.fetch_add(1);
                skrfeed::Shared* old = link_.exchange(fresh);
                const int oldCh = channel_;
                channel_ = want;
                if (old != nullptr)
                {
                    std::this_thread::sleep_for(std::chrono::milliseconds(100));   // the audio thread lets go
                    release(old, oldCh);
                }
            }
            if (effect_ != nullptr && host_ != nullptr && tick % 6 == 0) { notifyHostParameterChanged(kStatus); notifyHostParameterChanged(kMeter); }
            ++tick;
            std::this_thread::sleep_for(std::chrono::milliseconds(25));
        }
    }

    void release(skrfeed::Shared* s, int ch)
    {
        const uint32_t left = s->h.users.fetch_sub(1) - 1;
        skrfeed::unmapChannel(s);
        if (left == 0) skrfeed::removeChannel(ch);   // the name goes; SKRATCHA keeps its mapping until it lets go
    }

    void detach()
    {
        skrfeed::Shared* s = link_.exchange(nullptr);
        if (s != nullptr) release(s, channel_);
    }

    static mpc::PluginInfo makeInfo()
    {
        mpc::PluginInfo info;
        info.name = "SKRATCHA FEED";
        info.vendor = "JJ DA PLUG";
        info.uniqueId = MPC_FOURCC('J', 'J', 's', 'F');
        info.version = 1000;
        info.isInstrument = false;
        info.numInputs = 2;
        info.numOutputs = 2;
        info.tailSamples = 1;
        return info;
    }

    std::atomic<skrfeed::Shared*> link_{nullptr};
    int channel_ = -1;
    std::thread worker_;
    std::atomic<bool> stop_{false};
    double sr_ = 44100.0;
    int maxBlock_ = 512;
    float fadeStep_ = 0.004f, mixRet_ = 0.0f, peak_ = 0.0f;
    uint32_t lastSkrAlive_ = 0;
    int skrIdle_ = 1000000, uiTick_ = 0;
    bool live_ = false;
};

MPC_PLUGIN_ENTRY(SkratchaFeed)
