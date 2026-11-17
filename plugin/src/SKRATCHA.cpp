// SKRATCHA.cpp - a scratch turntable for the MPC, by JJ DA PLUG.
//
// SPDX-License-Identifier: MIT
//
// A direct-drive turntable in the style of a classic DJ deck. A record (a WAV sample) sits on the platter; the
// MPC's touch strip, the on-screen platter or a Q-Link moves the record under your hand; the pads are start/stop,
// a cut fader and cue points.
//
// SIGNAL FLOW
//
//   hand input ──► hand target position ──► critically damped follower ──┐
//   (touch strip as pitch bend / mod wheel, on-screen platter, Q-Link)    ├─► record position x (in file samples)
//   motor (start / brake ramps, pitch fader, 33/45, reverse) ────────────┘          │
//                                                                                  ▼
//   sample mip-map (6 band-limited levels) ──► cubic Hermite read at x, level chosen by |speed| ──► fader (cut)
//   ──► crackle (optional) ──► level ──► out L/R
//
// WHY IT IS ACCURATE AND SMOOTH
//   * Pitch bend from the touch strip is 14 bit and arrives sample-accurately; every event moves the hand target.
//   * The record does not jump to the target: it follows with a critically damped spring (SMOOTH, default 3 ms),
//     so the speed (= the pitch you hear) is continuous even though the strip sends steps.
//   * Fast scratches play the record many times faster than normal. Plain interpolation would alias (a harsh,
//     metallic fizz). The sample is stored as a mip-map: level k is the sample low-passed and decimated by 2^k.
//     The read picks the level that fits the current speed and cross-fades between two levels, so scratches stay
//     clean up to 32x speed at a few percent CPU.
//
// TOUCH STRIP (set the MPC's touch strip to PITCH BEND)
//   The first value after the strip was idle grabs the record where it is (no jump). Moving the finger moves the
//   record: STRIP RANGE is how far the record turns for the full strip length (180 degrees = a half turn = 0.9 s
//   of audio at 33). When the strip springs back to the centre (exactly 0), the hand lets go after 25 ms, unless
//   another value comes first, and the motor catches the record again (CATCH). RELEASE = TIMEOUT instead lets go
//   when no value has arrived for 120 ms, for strips that do not spring back. MOD WHEEL (CC 1 / 33) and the
//   SCRATCH parameter (strip in Q-LINK mode, or a Q-Link knob) work the same way with the timeout release.
//
// PADS (relative to PAD BASE, C1 = 36 by default; notes wrap every 16)
//   +0 START/STOP   +1 CUT (fader closed while held)   +2 HOLD (hand on the record while held)
//   +3 CUE (jump to the cue point)   +4 SET CUE (hold + a hot cue pad stores it)   +5 REVERSE
//   +6 33/45   +7 FADER on/off   +8..+15 HOT CUE 1..8 (jump; if empty, store)
//
// THREADS
//   process() never allocates, locks or touches files. A background thread loads WAVs, builds mip-maps, deletes
//   old samples and reports the live values (platter angle, strip LED, fader LED and pad-toggled buttons) to the
//   MPC about 30 times a second. Live values are reported from that thread, not from the audio thread, because
//   reports go through the MPC's UI thread and calling them from audio caused dropouts on a Live III.

#include "mpc_plugin.h"
#include "dsp/math.h"
#include "dsp/wav.h"

#include <algorithm>
#include <cctype>
#include <atomic>
#include <chrono>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#if defined(_WIN32)
  #include <io.h>
#else
  #include <dirent.h>
  #include <glob.h>
#endif

#ifndef SKRATCHA_LIVE_AUTOMATABLE
#define SKRATCHA_LIVE_AUTOMATABLE 0   // 1: report the live display values as automatable parameters
#endif

namespace {

// ---- record geometry ------------------------------------------------------------------------------------------
constexpr double kPi = 3.14159265358979323846;
constexpr double kRevPerSecond33 = (100.0 / 3.0) / 60.0;   // 33 1/3 rpm: one second of audio = 0.5556 turns
constexpr int    kMipLevels = 6;                            // 1x, 2x, 4x, 8x, 16x, 32x
constexpr int    kMaxSamples = 64;                          // entries of the SAMPLE list
constexpr double kMaxSeconds = 90.0;                        // longer files are cut (memory)
constexpr int    kNumHotCues = 8;

constexpr int kAngleFrames = 48;   // must match the slipmat print film strip in the skin (one turn)
constexpr int kStrobeFrames = 8;   // strobe ring film strip: one dot period
constexpr int kStrobeDots = 180;   // 180 dots x 0.5556 rev/s = 100 flashes/s (neon lamp on 50 Hz mains): still at 33 1/3, pitch 0
constexpr int kStripFrames = 33;   // strip LED film strip: frame 0 = untouched, 1..32 = position
constexpr float kMaxSpeed = 32.0f; // file samples per output sample, safety clamp

// ---- one loaded record ---------------------------------------------------------------------------------------
struct Record
{
    std::string name;
    uint32_t nameHash = 0;                     // FNV-1a of the file name: are cues still for this record?
    double sampleRate = 44100.0;
    int channels = 1;
    size_t length = 0;                         // level-0 frames
    std::vector<float> lv[kMipLevels][2];      // [level][channel]
    size_t len[kMipLevels] = {0, 0, 0, 0, 0, 0};
};

// A 31-tap windowed-sinc low-pass at a quarter of the sample rate (half of Nyquist), for 2:1 decimation.
struct HalfbandFir
{
    static constexpr int N = 31;
    float h[N];
    HalfbandFir()
    {
        const double fc = 0.225;   // cycles per sample, a little below 0.25 to keep the stop band clean
        double sum = 0.0;
        for (int i = 0; i < N; ++i)
        {
            const double m = i - (N - 1) * 0.5;
            const double sinc = (m == 0.0) ? 2.0 * fc : std::sin(2.0 * kPi * fc * m) / (kPi * m);
            const double w = 0.42 - 0.5 * std::cos(2.0 * kPi * i / (N - 1)) + 0.08 * std::cos(4.0 * kPi * i / (N - 1));
            h[i] = (float)(sinc * w); sum += h[i];
        }
        for (int i = 0; i < N; ++i) h[i] = (float)(h[i] / sum);
    }
};

void buildMips(Record& r)
{
    static const HalfbandFir fir;
    for (int k = 1; k < kMipLevels; ++k)
    {
        const size_t srcLen = r.len[k - 1];
        const size_t dstLen = (srcLen + 1) / 2;
        r.len[k] = dstLen;
        for (int c = 0; c < r.channels; ++c)
        {
            const std::vector<float>& s = r.lv[k - 1][c];
            std::vector<float>& d = r.lv[k][c];
            d.assign(dstLen, 0.0f);
            for (size_t j = 0; j < dstLen; ++j)
            {
                const long centre = (long)(2 * j);
                double acc = 0.0;
                for (int t = 0; t < HalfbandFir::N; ++t)
                {
                    const long idx = centre + t - (HalfbandFir::N - 1) / 2;
                    if (idx >= 0 && idx < (long)srcLen) acc += fir.h[t] * s[(size_t)idx];
                }
                d[j] = std::fabs(acc) < 1e-20 ? 0.0f : (float)acc;
            }
        }
    }
}

Record* loadRecord(const std::string& path, const std::string& name)
{
    ::dsp::WavData w;
    if (!::dsp::loadWav(path, w) || w.numFrames() < 16 || w.numChannels() < 1) return nullptr;
    Record* r = new Record();
    r->name = name;
    { uint32_t h = 2166136261u; for (unsigned char ch : path) { h ^= ch; h *= 16777619u; } r->nameHash = h ? h : 1u; }
    r->sampleRate = w.sampleRate > 1000.0 ? w.sampleRate : 44100.0;
    r->channels = w.numChannels() >= 2 ? 2 : 1;
    size_t n = w.numFrames();
    const size_t maxN = (size_t)(kMaxSeconds * r->sampleRate);
    if (n > maxN) n = maxN;
    r->length = n;
    r->len[0] = n;
    for (int c = 0; c < r->channels; ++c)
    {
        r->lv[0][c].assign(w.channels[(size_t)c].begin(), w.channels[(size_t)c].begin() + (long)n);
        for (float& v : r->lv[0][c]) v = std::isfinite(v) ? v : 0.0f;
    }
    buildMips(*r);
    return r;
}

std::string displayName(const std::string& file)
{
    std::string s = file;
    const size_t dot = s.find_last_of('.');
    if (dot != std::string::npos) s = s.substr(0, dot);
    // drop a leading "01 " / "01_" ordering prefix
    if (s.size() > 3 && std::isdigit((unsigned char)s[0]) && std::isdigit((unsigned char)s[1]) && (s[2] == ' ' || s[2] == '_' || s[2] == '-'))
        s = s.substr(3);
    for (char& ch : s) if (ch == '_') ch = ' ';
    if (s.size() > 22) s = s.substr(0, 22);
    return s;
}

bool hasWavExt(const std::string& f)
{
    if (f.size() < 5 || f[0] == '.') return false;
    std::string e = f.substr(f.size() - 4);
    for (char& ch : e) ch = (char)std::tolower((unsigned char)ch);
    return e == ".wav";
}

void listWavs(const std::string& dir, std::vector<std::string>& out)
{
    std::vector<std::string> found;
#if defined(_WIN32)
    struct _finddata_t fd;
    intptr_t h = _findfirst((dir + "/*.wav").c_str(), &fd);
    if (h != -1)
    {
        do { if (!(fd.attrib & _A_SUBDIR) && hasWavExt(fd.name)) found.push_back(dir + "/" + fd.name); } while (_findnext(h, &fd) == 0);
        _findclose(h);
    }
#else
    DIR* d = opendir(dir.c_str());
    if (d != nullptr)
    {
        while (dirent* e = readdir(d))
            if (hasWavExt(e->d_name)) found.push_back(dir + "/" + e->d_name);
        closedir(d);
    }
#endif
    std::sort(found.begin(), found.end());
    out.insert(out.end(), found.begin(), found.end());
}

inline float hermite(float xm1, float x0, float x1, float x2, float t)
{
    const float c1 = 0.5f * (x1 - xm1);
    const float c2 = xm1 - 2.5f * x0 + 2.0f * x1 - 0.5f * x2;
    const float c3 = 0.5f * (x2 - xm1) + 1.5f * (x0 - x1);
    return ((c3 * t + c2) * t + c1) * t + x0;
}

} // namespace

class SKRATCHA : public mpc::Plugin
{
public:
    enum Params
    {
        kLevel = 0, kSample, kPlay, kSpeed, kPitch, kPitchRange, kStart, kBrake,
        kStripRange, kStripDir, kRelease, kSmooth, kCatch, kCurve, kFader, kReverse,
        kCrackle, kPadBase, kLoop, kScratch, kJog, kAngle, kStripLed, kCutLed, kRescan, kStrobe,
        kNumParams
    };

    static mpc::PluginInfo makeInfo()
    {
        mpc::PluginInfo i;
        i.name = "SKRATCHA";
        i.vendor = "JJ DA PLUG";
        i.uniqueId = MPC_FOURCC('J', 'J', 's', 'K');   // == "uid" in plugin.json
        i.version = 1000;
        i.isInstrument = true;
        i.numInputs = 0;
        i.numOutputs = 2;
        return i;
    }

    SKRATCHA() : mpc::Plugin(makeInfo())
    {
        using namespace mpc;
        addParam(floatParam("level", "Level", -40.0f, 6.0f, -3.0f, "dB", 1));            // param 0: harmless (host nudges it)
        addParam(intParam("sample", "Sample", 1, kMaxSamples, 1));                       // which record is on the platter
        addParam(boolParam("play", "Start/Stop", false));                                 // motor on/off
        addParam(choiceParam("speed", "Speed", {"33", "45"}, 0));
        addParam(floatParam("pitch", "Pitch", -100.0f, 100.0f, 0.0f, "%", 1));            // pitch fader, % of PITCH RANGE
        addParam(choiceParam("prange", "Pitch Range", {"8%", "16%", "50%"}, 0));
        addParam(logParam("start", "Start Time", 30.0f, 3000.0f, 700.0f, "ms", 0));      // motor run-up
        addParam(logParam("brake", "Brake Time", 30.0f, 5000.0f, 900.0f, "ms", 0));      // motor run-down
        addParam(floatParam("srange", "Strip Range", 45.0f, 720.0f, 180.0f, "deg", 0));  // record turn for the whole strip
        addParam(choiceParam("sdir", "Strip Dir", {"NORMAL", "INVERT"}, 0));
        addParam(choiceParam("release", "Release", {"CENTER", "TIMEOUT"}, 0));           // how the strip lets go
        addParam(logParam("smooth", "Smooth", 0.5f, 20.0f, 3.0f, "ms", 1));              // hand follower time
        addParam(logParam("catch", "Catch", 10.0f, 500.0f, 90.0f, "ms", 0));             // motor grabs the record after release
        addParam(choiceParam("curve", "Cut Curve", {"SHARP", "MEDIUM", "SOFT"}, 0));     // fader ramp 0.7 / 3 / 12 ms
        addParam(boolParam("fader", "Fader", true));                                      // fader open
        addParam(boolParam("reverse", "Reverse", false));
        addParam(floatParam("crackle", "Crackle", 0.0f, 100.0f, 0.0f, "%", 0));
        addParam(choiceParam("padbase", "Pad Base", {"C1 36", "C#1 37"}, 0));
        addParam(boolParam("loop", "Loop", true));                                         // the record loops at its end
        addParam(floatParam("scratch", "Scratch", 0.0f, 100.0f, 50.0f, "%", 1));          // strip in Q-LINK mode / a knob
        Param jog = floatParam("jog", "Platter", 0.0f, 360.0f, 0.0f, "deg", 0);           // on-screen platter (absolute angle)
        jog.automatable = false; addParam(jog);
        Param ang = floatParam("angle", "Angle", 0.0f, 1.0f, 0.0f, "", 3);               // live: platter picture
        ang.automatable = SKRATCHA_LIVE_AUTOMATABLE != 0; addParam(ang);
        Param sl = intParam("stripled", "Strip LED", 0, kStripFrames - 1, 0);             // live: strip position LED
        sl.automatable = SKRATCHA_LIVE_AUTOMATABLE != 0; addParam(sl);
        Param cl = boolParam("cutled", "Cut LED", true);                                  // live: fader really open
        cl.automatable = SKRATCHA_LIVE_AUTOMATABLE != 0; addParam(cl);
        Param rs = boolParam("rescan", "Rescan", false);                                  // re-read the sample folders
        rs.automatable = false; addParam(rs);
        Param sb = floatParam("strobe", "Strobe", 0.0f, 1.0f, 0.0f, "", 3);              // live: strobe dot ring phase
        sb.automatable = SKRATCHA_LIVE_AUTOMATABLE != 0; addParam(sb);
        if (numParams() != kNumParams) mpc::log("SKRATCHA: parameter count mismatch");

        // ----- built-in programs (plain values in parameter order) -----
        auto base = [this]() { std::vector<float> v((size_t)numParams()); for (int i = 0; i < numParams(); ++i) v[(size_t)i] = param(i).def; return v; };
        std::vector<float> v = base();
        addProgram("INIT", v);
        v = base(); v[kSmooth] = 3.0f; v[kStripRange] = 180.0f; v[kCatch] = 90.0f; v[kPlay] = 1;
        addProgram("BABY SCRATCH", v);
        v = base(); v[kCurve] = 0; v[kSmooth] = 2.0f; v[kStripRange] = 150.0f;
        addProgram("TRANSFORMER", v);
        v = base(); v[kCurve] = 1; v[kSmooth] = 1.5f; v[kStripRange] = 240.0f;
        addProgram("CHIRP", v);
        v = base(); v[kStripRange] = 90.0f; v[kSmooth] = 8.0f; v[kStart] = 1500.0f; v[kBrake] = 2500.0f; v[kPlay] = 1;
        addProgram("SLOW DRAG", v);
        v = base(); v[kSpeed] = 1; v[kStripRange] = 270.0f; v[kSmooth] = 2.0f;
        addProgram("45 HYPE", v);
        v = base(); v[kCrackle] = 35.0f; v[kCurve] = 2; v[kSmooth] = 4.0f; v[kPlay] = 1;
        addProgram("DUSTY CRATE", v);
        v = base(); v[kStart] = 40.0f; v[kBrake] = 40.0f; v[kCatch] = 25.0f; v[kSmooth] = 1.0f;
        addProgram("TIGHT", v);

        scanFolders();
        requestedSample_.store(1);
    }

    ~SKRATCHA() override
    {
        stopThread_.store(true);
        if (worker_.joinable()) worker_.join();
        delete active_;
        delete pending_.exchange(nullptr);
        delete retired_.exchange(nullptr);
    }

    // ---------------------------------------------------------------------------------------------------------
    void prepare(double sampleRate, int /*maxBlockSize*/) override
    {
        sr_ = sampleRate > 1000.0 ? sampleRate : 44100.0;
        levelGain_ = mpc::dsp::dbToGain(get(kLevel));
        if (!threadStarted_)
        {
            // first load happens synchronously so a project opens with its record already on the platter
            if (Record* r = loadByIndex(requestedSample_.load())) { delete active_; active_ = r; loadedSample_.store(requestedSample_.load()); if (cueRecord_ == 0) cueRecord_ = r->nameHash; }
            threadStarted_ = true;
            worker_ = std::thread([this] { backgroundLoop(); });
        }
    }

    void reset() override
    {
        // after a state load or a program pick: take over cues, and do not mistake restored values for a hand
        if (cueStagingValid_.exchange(false)) { cue_ = cueStaging_; for (int i = 0; i < kNumHotCues; ++i) hot_[i] = hotStaging_[i]; cueRecord_ = cueRecordStaging_; }
        lastScratch_ = get(kScratch);
        lastJog_ = get(kJog);
        handActive_ = false; releasePending_ = 0; padHold_ = false; cutHeld_ = false; setCueHeld_ = false;
        faderGain_ = getBool(kFader) ? 1.0f : 0.0f;
        levelGain_ = mpc::dsp::dbToGain(get(kLevel));
        handVel_ = vel_;
    }

    // ---------------------------------------------------------------------------------------------------------
    void process(mpc::ProcessContext& ctx) override
    {
        // a freshly loaded record goes on the platter at the start of a block
        if (Record* fresh = pending_.exchange(nullptr))
        {
            Record* old = active_;
            active_ = fresh;
            if (old != nullptr) { Record* prev = retired_.exchange(old); delete prev; /* never happens: worker waits */ }
            x_ = 0.0; handTarget_ = 0.0; rawTarget_ = 0.0; interpLeft_ = 0; handVel_ = 0.0; xfade_ = 0.0f;
            if (fresh->nameHash != cueRecord_)
            {
                // another record: its cues start empty (a project load restores cues for the same record)
                cue_ = 0.0;
                for (int i = 0; i < kNumHotCues; ++i) hot_[i] = -1.0;
                cueRecord_ = fresh->nameHash;
            }
        }

        readBlockParams();
        eventClock_ = blockClock_;
        pollParamHands(ctx.numFrames);

        int pos = 0;
        for (int e = 0; e < ctx.numMidiEvents; ++e)
        {
            const mpc::MidiEvent& ev = ctx.midi[e];
            if (ev.sampleOffset > pos) { render(ctx, pos, ev.sampleOffset); pos = ev.sampleOffset; }
            eventClock_ = blockClock_ + ev.sampleOffset;
            handleMidi(ev);
        }
        render(ctx, pos, ctx.numFrames);
        blockClock_ += ctx.numFrames;

        // live values for the background reporter
        const double revs = (active_ != nullptr ? x_ / active_->sampleRate : x_ / sr_) * kRevPerSecond33;
        liveRevs_.store(revs);
        liveStrip_.store(handActive_ ? stripLedFrame_ : 0);
        liveCut_.store(faderGain_ > 0.5f);
        // the hand-follower state must not grow without bound when nothing plays
        if (!std::isfinite(x_)) { x_ = 0.0; handTarget_ = 0.0; rawTarget_ = 0.0; interpLeft_ = 0; handVel_ = 0.0; vel_ = 0.0; }
    }

    void parameterChanged(int index, float plainValue) override
    {
        if (index == kSample) requestedSample_.store((int)std::lround(plainValue));
        else if (index == kRescan && plainValue >= 0.5f) rescanRequested_.store(true);
    }

    bool formatValue(int index, float plainValue, std::string& out) override
    {
        if (index == kSample)
        {
            const int i = (int)std::lround(plainValue);
            std::lock_guard<std::mutex> lk(namesMutex_);
            out = (i >= 1 && i <= (int)names_.size()) ? names_[(size_t)(i - 1)] : std::string("-");
            return true;
        }
        if (index == kPitch)
        {
            static const float ranges[3] = {8.0f, 16.0f, 50.0f};
            const float pct = plainValue * 0.01f * ranges[mpc::clamp(getInt(kPitchRange), 0, 2)];
            char buf[24]; std::snprintf(buf, sizeof(buf), "%+.2f%%", (double)pct);
            out = buf; return true;
        }
        if (index == kStripRange) { char buf[24]; std::snprintf(buf, sizeof(buf), "%d deg", (int)std::lround(plainValue)); out = buf; return true; }
        if (index == kPlay) { out = plainValue >= 0.5f ? "PLAY" : "STOP"; return true; }
        if (index == kFader) { out = plainValue >= 0.5f ? "OPEN" : "CUT"; return true; }
        return false;
    }

    void saveExtraState(std::vector<uint8_t>& out) override
    {
        auto putD = [&out](double d) { uint8_t b[8]; std::memcpy(b, &d, 8); out.insert(out.end(), b, b + 8); };
        out.push_back('S'); out.push_back('K'); out.push_back(2);
        for (int k = 0; k < 4; ++k) out.push_back((uint8_t)(cueRecord_ >> (8 * k)));
        putD(cue_);
        for (int i = 0; i < kNumHotCues; ++i) putD(hot_[i]);
    }

    void loadExtraState(const uint8_t* data, size_t size) override
    {
        if (size < 7 + 8 * (1 + kNumHotCues) || data[0] != 'S' || data[1] != 'K' || data[2] != 2) return;
        size_t p = 3;
        uint32_t rh = 0; for (int k = 0; k < 4; ++k) rh |= (uint32_t)data[p++] << (8 * k);
        cueRecordStaging_ = rh;
        auto getD = [&](double& d) { std::memcpy(&d, data + p, 8); p += 8; if (!std::isfinite(d)) d = 0.0; };
        getD(cueStaging_);
        for (int i = 0; i < kNumHotCues; ++i) getD(hotStaging_[i]);
        cueStagingValid_.store(true);
    }

private:
    // ---------------------------------------------------------------------------------------------------------
    // parameters read once per block
    void readBlockParams()
    {
        static const float ranges[3] = {0.08f, 0.16f, 0.50f};
        const double fileSr = active_ != nullptr ? active_->sampleRate : sr_;
        unity_ = fileSr / sr_;                                         // file samples per output sample at normal speed
        const double speedRatio = getInt(kSpeed) == 1 ? 1.35 : 1.0;   // 45 / 33.333
        const double pitch = get(kPitch) * 0.01 * ranges[mpc::clamp(getInt(kPitchRange), 0, 2)];
        const double dir = getBool(kReverse) ? -1.0 : 1.0;
        motorTarget_ = getBool(kPlay) ? dir * speedRatio * (1.0 + pitch) * unity_ : 0.0;
        startStep_ = unity_ * speedRatio / std::max(1.0, get(kStart) * 0.001 * sr_);
        brakeStep_ = unity_ * speedRatio / std::max(1.0, get(kBrake) * 0.001 * sr_);
        catchCoef_ = 1.0 - std::exp(-1.0 / std::max(1.0, get(kCatch) * 0.001 * sr_));

        const double tau = std::max(8.0, get(kSmooth) * 0.001 * sr_);   // follower time constant in samples
        springK_ = 1.0 / (tau * tau);
        springD_ = 2.0 / tau;

        // hand scale: strip units are -1..+1 (half a strip per unit)
        const double samplesPerRev = fileSr / kRevPerSecond33;
        stripScale_ = (get(kStripRange) / 360.0) * samplesPerRev * 0.5 * (getInt(kStripDir) == 1 ? -1.0 : 1.0);
        samplesPerRev_ = samplesPerRev;

        static const float curveMs[3] = {0.7f, 3.0f, 12.0f};
        faderStep_ = 1.0f / std::max(1.0f, curveMs[mpc::clamp(getInt(kCurve), 0, 2)] * 0.001f * (float)sr_);
        levelTarget_ = mpc::dsp::dbToGain(get(kLevel));
        crackle_ = get(kCrackle) * 0.01f;
        loop_ = getBool(kLoop);
        timeoutRelease_ = getInt(kRelease) == 1;
        padBase_ = getInt(kPadBase) == 1 ? 37 : 36;
    }

    // the SCRATCH parameter (strip in Q-LINK mode, a Q-Link knob) and the on-screen platter move the hand too
    void pollParamHands(int frames)
    {
        const float s = get(kScratch);
        if (std::fabs(s - lastScratch_) > 1e-6f)
        {
            lastScratch_ = s;
            stripEvent((double)s * 0.02 - 1.0, kSrcScratch);
        }
        const float j = get(kJog);
        if (std::fabs(j - lastJog_) > 1e-6f)
        {
            double d = (double)(j - lastJog_) / 360.0;   // turns, wrap-aware (the knob jumps 360 -> 0)
            if (d > 0.5) d -= 1.0; else if (d < -0.5) d += 1.0;
            lastJog_ = j;
            jogEvent(d);
        }
        // timeout release for sources that never send "let go"
        if (handActive_ && !padHold_)
        {
            idleSamples_ += frames;
            const bool timeoutSource = handSrc_ != kSrcPitchBend || timeoutRelease_;
            const int limit = (int)(0.120 * sr_);
            if (timeoutSource && idleSamples_ > limit) letGo();
        }
    }

    enum Source { kSrcNone = 0, kSrcPitchBend, kSrcModWheel, kSrcScratch, kSrcJog, kSrcPad };

    void grab(Source src)
    {
        if (!handActive_)
        {
            handActive_ = true;
            handTarget_ = x_;
            rawTarget_ = x_;
            interpLeft_ = 0;
            lastEventClock_ = -1.0e12;      // the next event starts a new gesture (no interval yet)
            handVel_ = vel_;                // the hand meets the record at its current speed: no click
        }
        handSrc_ = src;
        idleSamples_ = 0;
        releasePending_ = 0;
    }

    void letGo()
    {
        handActive_ = false;
        releasePending_ = 0;
        vel_ = handVel_;                    // the record keeps the speed the hand gave it
        catching_ = motorTarget_ != 0.0;    // ... the running motor grabs it with the CATCH time (else it brakes)
        handSrc_ = kSrcNone;
    }

    // v in -1..+1 strip units
    void stripEvent(double v, Source src)
    {
        if (!handActive_ || handSrc_ != src || anchorSrc_ != src)
        {
            grab(src);
            anchorVal_ = v;
            anchorPos_ = rawTarget_;
            anchorSrc_ = src;
        }
        moveTarget(anchorPos_ + (v - anchorVal_) * stripScale_);
        idleSamples_ = 0;
        releasePending_ = 0;
        stripLedFrame_ = 1 + mpc::clamp((int)std::lround((v * 0.5 + 0.5) * (kStripFrames - 2)), 0, kStripFrames - 2);
    }

    void jogEvent(double turns)
    {
        if (!handActive_ || handSrc_ != kSrcJog) { grab(kSrcJog); anchorSrc_ = kSrcJog; }
        moveTarget(rawTarget_ + turns * samplesPerRev_ * (getInt(kStripDir) == 1 ? -1.0 : 1.0));
        idleSamples_ = 0;
        stripLedFrame_ = (kStripFrames - 1) / 2 + 1;
    }

    // A new hand position arrived. Controllers report every few ms in steps; jumping the target at each step would
    // put a buzz at the report rate on the pitch. Instead the target glides linearly to the new value over the
    // measured report interval (about 2 ms on the strip), and the spring smooths what is left.
    void moveTarget(double raw)
    {
        const double now = eventClock_;
        const double dt = now - lastEventClock_;
        lastEventClock_ = now;
        if (dt > 0.0 && dt < 0.025 * sr_)
            eventInterval_ += (mpc::clamp(dt, 0.0003 * sr_, 0.012 * sr_) - eventInterval_) * 0.3;
        rawTarget_ = raw;
        const double glide = (dt > 0.0 && dt < 0.025 * sr_) ? std::max(1.0, eventInterval_) : 1.0;
        interpLeft_ = (int)std::lround(glide);
        interpStep_ = (rawTarget_ - handTarget_) / (double)interpLeft_;
    }

    void handleMidi(const mpc::MidiEvent& ev)
    {
        if (ev.isPitchBend())
        {
            const int pb = ev.pitchBend();
            if (pb == 0)
            {
                // the strip springs back to the centre when the finger leaves: let go a moment later, unless the
                // finger only passed the centre (another value arrives first)
                if (handActive_ && handSrc_ == kSrcPitchBend && !timeoutRelease_) releasePending_ = (int)(0.025 * sr_);
                return;
            }
            stripEvent((double)pb / 8192.0, kSrcPitchBend);
        }
        else if (ev.isController())
        {
            if (ev.controller() == 1)       { mwMsb_ = ev.controllerValue(); mwLsb_ = 0; stripEvent(mwValue(), kSrcModWheel); }
            else if (ev.controller() == 33) { mwLsb_ = ev.controllerValue(); if (handSrc_ == kSrcModWheel) stripEvent(mwValue(), kSrcModWheel); }
            else if (ev.controller() == 120 || ev.controller() == 123) { cutHeld_ = false; padHold_ = false; setCueHeld_ = false; if (handActive_) letGo(); }
        }
        else if (ev.isNoteOn() || ev.isNoteOff())
        {
            const int f = (((ev.note() - padBase_) % 16) + 16) % 16;
            const bool on = ev.isNoteOn();
            handlePad(f, on);
        }
    }

    double mwValue() const { return ((double)((mwMsb_ << 7) | mwLsb_) / 16383.0) * 2.0 - 1.0; }

    void handlePad(int f, bool on)
    {
        switch (f)
        {
            case 0: if (on) toggleParam(kPlay); break;
            case 1: cutHeld_ = on; break;
            case 2:
                if (on) { padHold_ = true; grab(kSrcPad); anchorSrc_ = kSrcPad; rawTarget_ = handTarget_ = x_; interpLeft_ = 0; }
                else { padHold_ = false; if (handActive_ && (handSrc_ == kSrcPad)) letGo(); }
                break;
            case 3: if (on) jumpTo(cue_); break;
            case 4: setCueHeld_ = on; if (on) cue_ = x_; break;
            case 5: if (on) toggleParam(kReverse); break;
            case 6: if (on) toggleParam(kSpeed); break;
            case 7: if (on) toggleParam(kFader); break;
            default:
                if (on)
                {
                    const int h = f - 8;
                    if (setCueHeld_ || hot_[h] < 0.0) hot_[h] = x_;
                    else jumpTo(hot_[h]);
                }
                break;
        }
    }

    void toggleParam(int index)
    {
        set(index, getInt(index) == 0 ? 1.0f : 0.0f);
        dirty_.fetch_or(1u << index);           // the background thread tells the MPC (button lights)
        readBlockParamsLater_ = true;
    }

    void jumpTo(double pos)
    {
        // a cue jump: cross-fade 3 ms from the old position to the new one (no click)
        xOld_ = x_; xfade_ = 1.0f;
        const double shift = pos - x_;
        x_ = pos; handTarget_ += shift; rawTarget_ += shift; anchorPos_ += shift;
    }

    // ---------------------------------------------------------------------------------------------------------
    void render(mpc::ProcessContext& ctx, int from, int to)
    {
        if (readBlockParamsLater_) { readBlockParams(); readBlockParamsLater_ = false; }
        float* L = ctx.outputs[0];
        float* R = ctx.numOutputs > 1 ? ctx.outputs[1] : nullptr;
        const Record* rec = active_;
        const float xfadeStep = 1.0f / std::max(1.0f, 0.003f * (float)sr_);

        for (int i = from; i < to; ++i)
        {
            // --- hand ---
            if (releasePending_ > 0 && --releasePending_ == 0) letGo();
            if (handActive_)
            {
                if (interpLeft_ > 0) { handTarget_ += interpStep_; if (--interpLeft_ == 0) handTarget_ = rawTarget_; }
                // critically damped spring: the record follows the finger with continuous speed
                const double a = springK_ * (handTarget_ - x_) - springD_ * handVel_;
                handVel_ += a;
                if (handVel_ > kMaxSpeed) handVel_ = kMaxSpeed; else if (handVel_ < -kMaxSpeed) handVel_ = -kMaxSpeed;
                x_ += handVel_;
                vel_ = handVel_;
            }
            else
            {
                // --- motor ---
                if (catching_)
                {
                    vel_ += (motorTarget_ - vel_) * catchCoef_;
                    if (std::fabs(motorTarget_ - vel_) < 0.002 * unity_) { vel_ = motorTarget_; catching_ = false; }
                }
                else if (vel_ != motorTarget_)
                {
                    const bool speedingUp = std::fabs(motorTarget_) > std::fabs(vel_) && (motorTarget_ * vel_ >= 0.0);
                    const double step = speedingUp ? startStep_ : brakeStep_;
                    if (vel_ < motorTarget_) vel_ = std::min(motorTarget_, vel_ + step);
                    else vel_ = std::max(motorTarget_, vel_ - step);
                }
                x_ += vel_;
                handVel_ = vel_;
            }

            // --- read the record ---
            float sl = 0.0f, sr = 0.0f;
            if (rec != nullptr)
            {
                readAt(*rec, x_, std::fabs(vel_), sl, sr);
                if (xfade_ > 0.0f)
                {
                    float ol, orr; xOld_ += vel_;
                    readAt(*rec, xOld_, std::fabs(vel_), ol, orr);
                    sl += (ol - sl) * xfade_; sr += (orr - sr) * xfade_;
                    xfade_ = std::max(0.0f, xfade_ - xfadeStep);
                }
            }

            // --- crackle: dust pops, louder when the record moves ---
            if (crackle_ > 0.0f)
            {
                const float motion = (float)std::min(1.0, std::fabs(vel_) / std::max(1e-6, unity_));
                rng_ = rng_ * 1664525u + 1013904223u;
                const float u = (float)(rng_ >> 8) * (1.0f / 16777216.0f);
                if (u < crackle_ * 0.0006f * motion) popEnv_ = (0.15f + u * 400.0f) * crackle_;
                rng_ = rng_ * 1664525u + 1013904223u;
                const float n = ((float)(rng_ >> 8) * (1.0f / 8388608.0f)) - 1.0f;
                const float c = n * (popEnv_ + 0.004f * crackle_ * motion);
                popEnv_ *= 0.86f;
                sl += c; sr += c;
            }

            // --- fader (cut), cue declick, level ---
            const float fTarget = (getBool(kFader) && !cutHeld_) ? 1.0f : 0.0f;
            if (faderGain_ < fTarget) faderGain_ = std::min(fTarget, faderGain_ + faderStep_);
            else if (faderGain_ > fTarget) faderGain_ = std::max(fTarget, faderGain_ - faderStep_);
            levelGain_ += (levelTarget_ - levelGain_) * 0.0015f;
            const float g = faderGain_ * levelGain_;
            float ol = mpc::dsp::sanitize(sl * g), orr = mpc::dsp::sanitize(sr * g);
            if (std::fabs(ol) < 1e-20f) ol = 0.0f;
            if (std::fabs(orr) < 1e-20f) orr = 0.0f;
            L[i] = ol;
            if (R) R[i] = orr;
        }
    }

    // band-limited read: pick the mip level for the speed, cross-fade between two levels
    void readAt(const Record& r, double pos, double speed, float& outL, float& outR) const
    {
        // Level k holds content up to about 9.9 kHz / 2^(k-1) (level 0: everything). Played at speed s, content f
        // comes out at f*s; above Nyquist it folds back to 44.1k - f*s. Keep every fold above ~15 kHz (inaudible,
        // and that band carries little energy): the lower of the two blended levels must satisfy fc * s <= 29 kHz.
        //   s <= 1      level 0 only (full bandwidth at normal speed)
        //   1 .. 1.45   fade level 0 -> 1
        //   > 1.45      lvl = log2(s) + 0.45, so floor(lvl) is always a safe level
        double lvl;
        if (speed <= 1.0) lvl = 0.0;
        else if (speed <= 1.45) lvl = (speed - 1.0) * (0.986 / 0.45);
        else lvl = std::log2(speed) + 0.45;
        float aL, aR;
        if (lvl >= kMipLevels - 1) { readLevel(r, kMipLevels - 1, pos, outL, outR); return; }
        const int L0 = (int)lvl;
        const float t = (float)(lvl - L0);
        readLevel(r, L0, pos, aL, aR);
        if (t > 0.001f) { float bL, bR; readLevel(r, L0 + 1, pos, bL, bR); aL += (bL - aL) * t; aR += (bR - aR) * t; }
        outL = aL; outR = aR;
    }

    void readLevel(const Record& r, int level, double pos0, float& outL, float& outR) const
    {
        const size_t n = r.len[level];
        const double scale = 1.0 / (double)(1u << level);
        double p = pos0 * scale;
        const double total = (double)n;
        if (loop_)
        {
            p = std::fmod(p, total);
            if (p < 0.0) p += total;
        }
        else if (p < -2.0 || p >= total + 2.0) { outL = outR = 0.0f; return; }
        const double fl = std::floor(p);
        const long i0 = (long)fl;
        const float t = (float)(p - fl);
        auto at = [&](const std::vector<float>& v, long i) -> float
        {
            if (loop_) { i %= (long)n; if (i < 0) i += (long)n; return v[(size_t)i]; }
            return (i >= 0 && i < (long)n) ? v[(size_t)i] : 0.0f;
        };
        const std::vector<float>& cl = r.lv[level][0];
        outL = hermite(at(cl, i0 - 1), at(cl, i0), at(cl, i0 + 1), at(cl, i0 + 2), t);
        if (r.channels > 1)
        {
            const std::vector<float>& cr = r.lv[level][1];
            outR = hermite(at(cr, i0 - 1), at(cr, i0), at(cr, i0 + 1), at(cr, i0 + 2), t);
        }
        else outR = outL;
    }

    // ---------------------------------------------------------------------------------------------------------
    // background thread: loading, cleanup, live display
    void scanFolders()
    {
        std::vector<std::string> paths;
        listWavs(mpc::contentPath("Samples"), paths);                       // built-in records
        const std::string folder = mpc::pluginFolder();
        if (!folder.empty()) listWavs(folder + "/My Samples", paths);        // drop WAVs here (inside the plugin folder)
#if !defined(_WIN32)
        // ... or into "MPC Documents/SKRATCHA" on any drive
        std::vector<std::string> dirs = {"/nvme/MPC Documents/SKRATCHA", "/sdcard/MPC Documents/SKRATCHA"};
        glob_t g;
        if (glob("/media/*/MPC Documents/SKRATCHA", 0, nullptr, &g) == 0)
        {
            for (size_t i = 0; i < g.gl_pathc; ++i) dirs.push_back(g.gl_pathv[i]);
            globfree(&g);
        }
        for (const std::string& d : dirs) listWavs(d, paths);
#endif
        if (paths.size() > (size_t)kMaxSamples) paths.resize((size_t)kMaxSamples);
        std::vector<std::string> names;
        for (const std::string& p : paths) names.push_back(displayName(p.substr(p.find_last_of("/\\") == std::string::npos ? 0 : p.find_last_of("/\\") + 1)));
        std::lock_guard<std::mutex> lk(namesMutex_);
        paths_ = paths;
        names_ = names;
    }

    Record* loadByIndex(int index)
    {
        std::string path, name;
        {
            std::lock_guard<std::mutex> lk(namesMutex_);
            if (index < 1 || index > (int)paths_.size()) return nullptr;
            path = paths_[(size_t)(index - 1)];
            name = names_[(size_t)(index - 1)];
        }
        return loadRecord(path, name);
    }

    void backgroundLoop()
    {
        int tick = 0;
        float lastAngle = -1.0f, lastStrobe = -1.0f; int lastStrip = -1; int lastCut = -1;
        const auto t0 = std::chrono::steady_clock::now();
        while (!stopThread_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(15));
            ++tick;

            delete retired_.exchange(nullptr);

            if (rescanRequested_.exchange(false))
            {
                scanFolders();
                loadedSample_.store(-1);     // reload the current entry (the list may have shifted)
                needDisplayUpdate_.store(true);
            }

            const int want = requestedSample_.load();
            if (want != loadedSample_.load() && pending_.load() == nullptr && retired_.load() == nullptr)
            {
                Record* r = loadByIndex(want);
                loadedSample_.store(want);
                if (r != nullptr) pending_.store(r);
                needDisplayUpdate_.store(true);
            }

            if (effect_ == nullptr || host_ == nullptr) continue;

            // ~33 Hz live display
            if ((tick & 1) == 0)
            {
                const double revs = liveRevs_.load();
                const float a = (float)(revs - std::floor(revs));
                float da = std::fabs(a - lastAngle);
                if (da > 0.5f) da = 1.0f - da;                       // circular distance
                if (lastAngle < 0.0f || da >= 0.5f / kAngleFrames)
                {
                    lastAngle = a;
                    setNormalised(kAngle, a);
                    notifyHostParameterChanged(kAngle);
                }
                // strobe: a neon lamp on 50 Hz mains flashes 100 times a second; the ring shows its phase against that
                const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
                double ph = revs * kStrobeDots - secs * 100.0;
                const float sp = (float)(ph - std::floor(ph));
                float ds = std::fabs(sp - lastStrobe); if (ds > 0.5f) ds = 1.0f - ds;
                if (lastStrobe < 0.0f || ds >= 0.5f / kStrobeFrames)
                {
                    lastStrobe = sp;
                    setNormalised(kStrobe, sp);
                    notifyHostParameterChanged(kStrobe);
                }
                const int s = liveStrip_.load();
                if (s != lastStrip) { lastStrip = s; set(kStripLed, (float)s); notifyHostParameterChanged(kStripLed); }
                const int c = liveCut_.load() ? 1 : 0;
                if (c != lastCut) { lastCut = c; set(kCutLed, (float)c); notifyHostParameterChanged(kCutLed); }
                const uint32_t d = dirty_.exchange(0u);
                for (int i = 0; i < kNumParams; ++i) if (d & (1u << i)) notifyHostParameterChanged(i);
                if (getBool(kRescan)) { set(kRescan, 0.0f); notifyHostParameterChanged(kRescan); }
            }
            if (needDisplayUpdate_.exchange(false)) requestDisplayUpdate();
        }
    }

    // ---------------------------------------------------------------------------------------------------------
    double sr_ = 44100.0, unity_ = 1.0;
    // record motion
    double x_ = 0.0, vel_ = 0.0, motorTarget_ = 0.0, startStep_ = 0.0, brakeStep_ = 0.0, catchCoef_ = 0.01;
    bool catching_ = false;
    // hand
    bool handActive_ = false, padHold_ = false;
    Source handSrc_ = kSrcNone, anchorSrc_ = kSrcNone;
    double handTarget_ = 0.0, handVel_ = 0.0, anchorPos_ = 0.0, anchorVal_ = 0.0;
    double rawTarget_ = 0.0, interpStep_ = 0.0, eventInterval_ = 88.0, lastEventClock_ = -1.0e12;
    double blockClock_ = 0.0, eventClock_ = 0.0;   // running sample count (for report intervals)
    int interpLeft_ = 0;
    double springK_ = 0.0, springD_ = 0.0, stripScale_ = 1.0, samplesPerRev_ = 79380.0;
    int releasePending_ = 0, idleSamples_ = 0, stripLedFrame_ = 0;
    bool timeoutRelease_ = false;
    float lastScratch_ = 50.0f, lastJog_ = 0.0f;
    int mwMsb_ = 64, mwLsb_ = 0;
    // pads, fader, cues
    int padBase_ = 36;
    bool cutHeld_ = false, setCueHeld_ = false, readBlockParamsLater_ = false;
    float faderGain_ = 1.0f, faderStep_ = 0.01f, xfade_ = 0.0f;
    double xOld_ = 0.0;
    uint32_t cueRecord_ = 0, cueRecordStaging_ = 0;
    double cue_ = 0.0, hot_[kNumHotCues] = {-1, -1, -1, -1, -1, -1, -1, -1};
    double cueStaging_ = 0.0, hotStaging_[kNumHotCues] = {-1, -1, -1, -1, -1, -1, -1, -1};
    std::atomic<bool> cueStagingValid_{false};
    // output
    float levelGain_ = 0.7f, levelTarget_ = 0.7f, crackle_ = 0.0f, popEnv_ = 0.0f;
    uint32_t rng_ = 0x2545F491u;
    bool loop_ = true;
    // records and threads
    Record* active_ = nullptr;                 // audio thread only
    std::atomic<Record*> pending_{nullptr};    // worker -> audio
    std::atomic<Record*> retired_{nullptr};    // audio -> worker (deleted there)
    std::atomic<int> requestedSample_{1}, loadedSample_{0};
    std::atomic<bool> rescanRequested_{false}, needDisplayUpdate_{false}, stopThread_{false};
    std::mutex namesMutex_;                    // never taken on the audio thread
    std::vector<std::string> paths_, names_;
    std::thread worker_;
    bool threadStarted_ = false;
    // live display values (audio -> background reporter)
    std::atomic<double> liveRevs_{0.0};
    std::atomic<int> liveStrip_{0};
    std::atomic<bool> liveCut_{true};
    std::atomic<uint32_t> dirty_{0u};
};

MPC_PLUGIN_ENTRY(SKRATCHA)
