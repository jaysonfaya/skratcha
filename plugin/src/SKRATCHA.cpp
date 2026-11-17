// SKRATCHA.cpp - two scratch turntables, a battle crossfader and a scratch teacher for the MPC, by JJ DA PLUG.
//
// SPDX-License-Identifier: MIT
//
// SIGNAL FLOW (per deck, two decks run at the same time)
//
//   hand input ──► hand target ──► critically damped follower ──┐
//   (touch strip, on-screen record, Q-Link, the teacher's DEMO)  ├─► record position x
//   motor (start / brake / catch, pitch, 33/45, reverse, wow) ──┘          │
//                                    TURNTABLE STYLE scales torque, platter mass, wow & flutter, tone
//                                                                          ▼
//   8 slots, each a sample mip-map (6 band-limited levels) ──► Hermite read at x, level by |speed|
//   ──► style tone (belt: warm + rumble) ──► crackle ──► channel on × volume × CROSSFADER curve × CUT pad
//   ──► mix A + B (+ browser preview, + teacher click) ──► level ──► out L/R
//
// THE HAND
//   Only the ACTIVE deck (DECK A / B, chosen explicitly with the deck buttons or pad 12) listens to the touch
//   strip and the screen. The first strip value grabs the record where it is; moving the finger moves the record
//   (STRIP RANGE = how far for the whole strip). When the strip springs back to the centre the hand lets go 25 ms
//   later (RELEASE = TIMEOUT: 120 ms after the last value instead) and the motor catches the record (CATCH).
//   Strip steps glide over the measured report interval, then a critically damped spring (SMOOTH × platter mass)
//   makes the speed continuous: no zipper, no clicks.
//
// CROSSFADER
//   Position 0 = deck A, 100 = deck B. CURVE 0 = a smooth constant-power blend over the whole travel; 100 = a
//   razor scratch cut: the deck is fully open 1.5 % from its closed end. CUT LAG is a dead zone at the closed end
//   (no bleed). HAMSTER swaps the sides. The CUT pad (pad 10) is the fastest fader: with CUT MODE = CLOSE holding
//   it closes the active deck, with OPEN the active deck only sounds while it is held (forwards, chirps,
//   transformers). CUT SPEED is how hard that cut is (0.7 / 3 / 12 ms ramp).
//
// PADS (relative to PAD BASE, C1 = 36 by default; notes wrap every 16)
//   1..8  SLOT 1..8 of the active deck: puts that sample on the platter at its cue (FIRE = PLAY also starts it)
//   9 START/STOP   10 CUT   11 HOLD (hand on the record)   12 DECK A/B
//   13 CUE (back to the cue)   14 SET CUE   15 REVERSE   16 33/45
//
// THREADS
//   process() never allocates, locks or touches files. A background thread scans the drives for the browser,
//   loads WAVs into slots, deletes replaced samples, and reports the live values (record angle, strobe, LEDs,
//   teacher ghost, texts) to the MPC about 30 times a second - from that thread, not the audio thread, because
//   reports go through the MPC's UI thread and calling them from audio caused dropouts on a Live III.

#include "mpc_plugin.h"
#include "mpc_resources.h"
#include "dsp/math.h"

#include "skr_record.h"
#include "skr_helper.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#ifndef SKRATCHA_LIVE_AUTOMATABLE
#define SKRATCHA_LIVE_AUTOMATABLE 0   // 1: report the live display values as automatable parameters
#endif

using namespace skr;

namespace {

constexpr double kRevPerSecond33 = (100.0 / 3.0) / 60.0;   // 33 1/3 rpm
constexpr int kSlots = 8;
constexpr int kAngleFrames = 48;     // record film strip in the skin (one turn)
constexpr int kStrobeFrames = 8;
constexpr int kStrobeDots = 180;
constexpr int kStripFrames = 33;
constexpr int kNumStyles = 3;
constexpr float kMaxSpeed = 32.0f;

// ---- turntable styles: same controls, different machine -------------------------------------------------------
struct Style
{
    const char* name;
    float torque;      // × START time (lower = stronger motor)
    float brake;       // × BRAKE time
    float catchMul;    // × CATCH time (belt: slips, catches late)
    float mass;        // × SMOOTH (heavier platter = more inertia under the hand)
    float wow, wowHz, flutter, flutterHz;   // speed wobble (fraction of speed)
    float lpHz;        // tone (0 = full range)
    float rumble;      // motor/bearing rumble level
    float dust;        // extra crackle
};
const Style kStyles[kNumStyles] = {
    {"DD SILBER",   1.00f, 1.00f, 1.00f, 1.00f, 0.00045f, 0.55f, 0.00020f, 7.5f,     0.0f, 0.000f, 0.00f},
    {"BATTLE",      0.22f, 0.28f, 0.45f, 0.72f, 0.00020f, 0.55f, 0.00010f, 9.0f,     0.0f, 0.000f, 0.00f},
    {"RIEMEN 70ER", 3.20f, 2.60f, 3.00f, 1.45f, 0.00280f, 0.50f, 0.00120f, 6.2f,  9500.0f, 0.006f, 0.12f},
};

std::string fmt(const char* f, double v) { char b[48]; std::snprintf(b, sizeof(b), f, v); return b; }

} // namespace

class SKRATCHA : public mpc::Plugin
{
public:
    enum Params
    {
        // ---- 1.0 parameters (order and ids are permanent; deck A unless noted) ----
        kLevel = 0, kSample, kPlay, kSpeed, kPitch, kPitchRange, kStart, kBrake,
        kStripRange, kStripDir, kRelease, kSmooth, kCatch, kCurve, kFader, kReverse,
        kCrackle, kPadBase, kLoop, kScratch, kJog, kAngle, kStripLed, kCutLed, kRescan, kStrobe,
        // ---- 2.0 ----
        kDeck, kXFader, kXCurve, kXLag, kHamster, kCutMode, kMode, kASlot, kBSlot, kAStyle, kBStyle, kAVol, kBVol,
        kBPlay, kBSpeed, kBPitch, kBPitchRange, kBStart, kBBrake, kBFader, kBReverse, kBLoop, kBAngle, kBCutLed, kBStrobe,
        kAName, kBName, kANames, kBNames = kANames + kSlots,
        kBrFolder = kBNames + kSlots, kBrFile, kBrRows, kBrInfo = kBrRows + 5, kBrPreview, kBrLoad, kBrFolderName,
        kHLesson, kHRun, kHDemo, kHBpm, kHClick, kHGhost, kHBeat, kHStars, kHMsg, kHText1, kHText2, kHScore, kHFadeLed,
        kFireMode,
        kNumParams
    };

    struct DeckParams { int play, speed, pitch, prange, start, brake, chan, reverse, loop, angle, cutled, strobe, slot, style, vol, name, names; };

    static mpc::PluginInfo makeInfo()
    {
        mpc::PluginInfo i;
        i.name = "SKRATCHA";
        i.vendor = "JJ DA PLUG";
        i.uniqueId = MPC_FOURCC('J', 'J', 's', 'K');   // == "uid" in plugin.json
        i.version = 2000;
        i.isInstrument = true;
        i.numInputs = 0;
        i.numOutputs = 2;
        return i;
    }

    SKRATCHA() : mpc::Plugin(makeInfo())
    {
        using namespace mpc;
        auto live = [](Param p) { p.automatable = SKRATCHA_LIVE_AUTOMATABLE != 0; return p; };
        auto fixed = [](Param p) { p.automatable = false; return p; };
        const std::vector<std::string> slotNames = {"1", "2", "3", "4", "5", "6", "7", "8"};
        const std::vector<std::string> styleNames = {kStyles[0].name, kStyles[1].name, kStyles[2].name};

        addParam(floatParam("level", "Level", -40.0f, 6.0f, -3.0f, "dB", 1));            // param 0: harmless (host nudges it)
        addParam(fixed(intParam("sample", "Sample (1.0)", 1, 64, 1)));                   // 1.0 only, unused
        addParam(boolParam("play", "A Start/Stop", false));
        addParam(choiceParam("speed", "A Speed", {"33", "45"}, 0));
        addParam(floatParam("pitch", "A Pitch", -100.0f, 100.0f, 0.0f, "%", 1));
        addParam(choiceParam("prange", "A Pitch Rng", {"8%", "16%", "50%"}, 0));
        addParam(logParam("start", "A Start Time", 30.0f, 3000.0f, 700.0f, "ms", 0));
        addParam(logParam("brake", "A Brake Time", 30.0f, 5000.0f, 900.0f, "ms", 0));
        addParam(floatParam("srange", "Strip Range", 45.0f, 720.0f, 180.0f, "deg", 0));  // record turn for the whole strip
        addParam(choiceParam("sdir", "Strip Dir", {"NORMAL", "INVERT"}, 0));
        addParam(choiceParam("release", "Release", {"CENTER", "TIMEOUT"}, 0));
        addParam(logParam("smooth", "Smooth", 0.5f, 20.0f, 3.0f, "ms", 1));
        addParam(logParam("catch", "Catch", 10.0f, 500.0f, 90.0f, "ms", 0));
        addParam(choiceParam("curve", "Cut Speed", {"SHARP", "MEDIUM", "SOFT"}, 0));     // CUT pad ramp 0.7 / 3 / 12 ms
        addParam(boolParam("fader", "A On", true));                                       // deck A channel on
        addParam(boolParam("reverse", "A Reverse", false));
        addParam(floatParam("crackle", "Crackle", 0.0f, 100.0f, 0.0f, "%", 0));
        addParam(choiceParam("padbase", "Pad Base", {"C1 36", "C#1 37"}, 0));
        addParam(boolParam("loop", "A Loop", false));
        addParam(floatParam("scratch", "Scratch", 0.0f, 100.0f, 50.0f, "%", 1));          // strip in Q-LINK mode / a knob
        addParam(fixed(floatParam("jog", "Platter", 0.0f, 360.0f, 0.0f, "deg", 0)));     // on-screen record
        addParam(live(floatParam("angle", "A Angle", 0.0f, 1.0f, 0.0f, "", 3)));
        addParam(live(intParam("stripled", "Strip LED", 0, kStripFrames - 1, 0)));
        addParam(live(boolParam("cutled", "A Cut LED", true)));
        addParam(fixed(boolParam("rescan", "Rescan", false)));
        addParam(live(floatParam("strobe", "A Strobe", 0.0f, 1.0f, 0.0f, "", 3)));
        // ---- 2.0 ----
        addParam(choiceParam("deck", "Deck", {"A", "B"}, 0));                               // explicit: the active deck
        addParam(floatParam("xfader", "Crossfader", 0.0f, 100.0f, 0.0f, "", 0));            // 0 = A, 100 = B
        addParam(floatParam("xcurve", "Fader Curve", 0.0f, 100.0f, 85.0f, "%", 0));        // 0 smooth .. 100 razor
        addParam(floatParam("xlag", "Cut Lag", 0.0f, 10.0f, 1.0f, "%", 1));
        addParam(boolParam("hamster", "Hamster", false));
        addParam(choiceParam("cutmode", "Cut Mode", {"CLOSE", "OPEN"}, 0));
        addParam(choiceParam("mode", "Mode", {"SIMPLE", "ADVANCED"}, 0));
        addParam(choiceParam("aslot", "A Slot", slotNames, 0));
        addParam(choiceParam("bslot", "B Slot", slotNames, 0));
        addParam(choiceParam("astyle", "A Style", styleNames, 0));
        addParam(choiceParam("bstyle", "B Style", styleNames, 1));
        addParam(floatParam("avol", "A Volume", -40.0f, 6.0f, 0.0f, "dB", 1));
        addParam(floatParam("bvol", "B Volume", -40.0f, 6.0f, 0.0f, "dB", 1));
        addParam(boolParam("bplay", "B Start/Stop", false));
        addParam(choiceParam("bspeed", "B Speed", {"33", "45"}, 0));
        addParam(floatParam("bpitch", "B Pitch", -100.0f, 100.0f, 0.0f, "%", 1));
        addParam(choiceParam("bprange", "B Pitch Rng", {"8%", "16%", "50%"}, 0));
        addParam(logParam("bstart", "B Start Time", 30.0f, 3000.0f, 700.0f, "ms", 0));
        addParam(logParam("bbrake", "B Brake Time", 30.0f, 5000.0f, 900.0f, "ms", 0));
        addParam(boolParam("bfader", "B On", true));
        addParam(boolParam("breverse", "B Reverse", false));
        addParam(boolParam("bloop", "B Loop", false));
        addParam(live(floatParam("bangle", "B Angle", 0.0f, 1.0f, 0.0f, "", 3)));
        addParam(live(boolParam("bcutled", "B Cut LED", true)));
        addParam(live(floatParam("bstrobe", "B Strobe", 0.0f, 1.0f, 0.0f, "", 3)));
        // text displays: the value is a change counter, formatValue() gives the text
        auto text = [&](const char* id, const char* name) { addParam(fixed(floatParam(id, name, 0.0f, 1.0f, 0.0f, "", 2))); };
        text("aname", "A Record"); text("bname", "B Record");
        for (int d = 0; d < 2; ++d)
            for (int s = 0; s < kSlots; ++s)
            {
                const std::string id = std::string(d ? "bn" : "an") + std::to_string(s + 1);
                const std::string nm = std::string(d ? "B" : "A") + " Slot " + std::to_string(s + 1) + " Name";
                addParam(fixed(floatParam(id.c_str(), nm.c_str(), 0.0f, 1.0f, 0.0f, "", 2)));
            }
        addParam(fixed(intParam("brfolder", "Folder", 1, BrowserIndex::kMaxFolders, 1)));
        addParam(fixed(intParam("brfile", "File", 1, BrowserIndex::kMaxFilesPerFolder, 1)));
        for (int r = 0; r < 5; ++r) { const std::string id = "brrow" + std::to_string(r); text(id.c_str(), ("Row " + std::to_string(r + 1)).c_str()); }
        text("brinfo", "Browser Info");
        addParam(fixed(boolParam("brpreview", "Preview", false)));
        addParam(fixed(choiceParam("brload", "Load To Slot", {"-", "1", "2", "3", "4", "5", "6", "7", "8"}, 0)));
        text("brfname", "Folder Name");
        std::vector<std::string> lessonNames; for (const Lesson& l : kLessons) lessonNames.push_back(l.name);
        addParam(fixed(choiceParam("hlesson", "Lesson", lessonNames, 0)));
        addParam(fixed(boolParam("hrun", "Lesson Start", false)));
        addParam(fixed(boolParam("hdemo", "Lesson Demo", false)));
        addParam(fixed(floatParam("hbpm", "Lesson BPM", 60.0f, 110.0f, 80.0f, "BPM", 0)));
        addParam(fixed(boolParam("hclick", "Click", true)));
        addParam(live(intParam("hghost", "Ghost", 0, kStripFrames - 1, 0)));
        addParam(live(intParam("hbeat", "Beat", 0, 8, 0)));
        addParam(live(intParam("hstars", "Stars", 0, 3, 0)));
        text("hmsg", "Tip"); text("htext1", "Lesson Text 1"); text("htext2", "Lesson Text 2"); text("hscore", "Score");
        addParam(live(boolParam("hfadeled", "Fader Target", false)));
        addParam(choiceParam("firemode", "Fire", {"CUE", "PLAY"}, 1));
        if (numParams() != kNumParams) mpc::log("SKRATCHA: parameter count mismatch %d %d", numParams(), (int)kNumParams);

        deckP_[0] = {kPlay, kSpeed, kPitch, kPitchRange, kStart, kBrake, kFader, kReverse, kLoop, kAngle, kCutLed, kStrobe, kASlot, kAStyle, kAVol, kAName, kANames};
        deckP_[1] = {kBPlay, kBSpeed, kBPitch, kBPitchRange, kBStart, kBBrake, kBFader, kBReverse, kBLoop, kBAngle, kBCutLed, kBStrobe, kBSlot, kBStyle, kBVol, kBName, kBNames};

        buildPrograms();

        // built-in records fill the slots until the user loads others (or a project restores its own)
        builtInDir_ = mpc::contentPath("Samples");
        std::vector<std::string> builtIns;
        listWavs(builtInDir_, builtIns);
        for (int s = 0; s < kSlots && !builtIns.empty(); ++s)
        {
            want_[0][s] = builtIns[(size_t)s % builtIns.size()];
            want_[1][s] = builtIns[(size_t)(s + 4) % builtIns.size()];   // deck B starts on the break
        }
        if (const char* t = std::getenv("SKRATCHA_TEST_SLOT8")) want_[0][7] = t;   // test harness only
    }

    ~SKRATCHA() override
    {
        stopThread_.store(true);
        if (worker_.joinable()) worker_.join();
        for (int d = 0; d < 2; ++d)
            for (int s = 0; s < kSlots; ++s)
            {
                delete deck_[d].slot[s];
                delete pending_[d][s].exchange(nullptr);
                delete retired_[d][s].exchange(nullptr);
            }
        delete preview_; delete previewPending_.exchange(nullptr); delete previewRetired_.exchange(nullptr);
    }

    // ---------------------------------------------------------------------------------------------------------
    void prepare(double sampleRate, int /*maxBlockSize*/) override
    {
        sr_ = sampleRate > 1000.0 ? sampleRate : 44100.0;
        levelGain_ = mpc::dsp::dbToGain(get(kLevel));
        if (!threadStarted_)
        {
            // first loads happen synchronously so a project opens with its records already on the platters
            loadWantedSlots(true);
            for (int d = 0; d < 2; ++d)
                for (int s = 0; s < kSlots; ++s)
                    if (Record* r = pending_[d][s].exchange(nullptr)) deck_[d].slot[s] = r;
            for (int d = 0; d < 2; ++d) deck_[d].cur = mpc::clamp(getInt(deckP_[d].slot), 0, kSlots - 1);
            threadStarted_ = true;
            worker_ = std::thread([this] { backgroundLoop(); });
        }
    }

    void reset() override
    {
        if (cueStagingValid_.exchange(false))
            for (int d = 0; d < 2; ++d) for (int s = 0; s < kSlots; ++s) deck_[d].cue[s] = cueStaging_[d][s];
        lastScratch_ = get(kScratch);
        lastJog_ = get(kJog);
        cutHeld_ = false; setCueHeld_ = false; padHold_ = false; releasePending_ = 0;
        for (Deck& D : deck_) { D.handActive = false; D.handVel = D.vel; }
        levelGain_ = mpc::dsp::dbToGain(get(kLevel));
        activeDeck_ = mpc::clamp(getInt(kDeck), 0, 1);
        // a loaded state or program shows its slots without "firing" them, and does not start a lesson's set-up
        for (int d = 0; d < 2; ++d) deck_[d].cur = mpc::clamp(getInt(deckP_[d].slot), 0, kSlots - 1);
        prevDemo_ = getBool(kHDemo); prevRun_ = getBool(kHRun);
        teacher_.stop();
        if (prevDemo_ || prevRun_) { teacher_.demo = prevDemo_; teacher_.start(mpc::clamp(getInt(kHLesson), 0, kNumLessons - 1)); }
    }

    // ---------------------------------------------------------------------------------------------------------
    void process(mpc::ProcessContext& ctx) override
    {
        swapIn();
        readBlockParams(ctx.numFrames);
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
        for (int d = 0; d < 2; ++d)
        {
            Deck& D = deck_[d];
            if (!std::isfinite(D.x)) { D.x = 0.0; D.handTarget = D.rawTarget = 0.0; D.interpLeft = 0; D.handVel = D.vel = 0.0; }
            const Record* r = D.slot[D.cur];
            liveRevs_[d].store((r != nullptr ? D.x / r->sampleRate : D.x / sr_) * kRevPerSecond33);
            liveCut_[d].store(D.audible * D.cutGain > 0.3f);
            liveSlot_[d].store(D.cur);
        }
        Deck& A = deck_[activeDeck_];
        liveStrip_.store(A.handActive ? stripLedFrame_ : 0);
        liveActive_.store(activeDeck_);
        liveGhost_.store(teacher_.running ? 1 + mpc::clamp((int)std::lround((teacher_.ghost * 0.5f + 0.5f) * (kStripFrames - 2)), 0, kStripFrames - 2) : 0);
        liveBeat_.store(teacher_.running ? teacher_.beat : 0);
        liveFadeLed_.store(teacher_.running && teacher_.faderTarget);
        liveMsg_.store(teacher_.msg);
        liveScore_.store(teacher_.scorePct + 1000 * teacher_.bar);
        if (teacher_.starsNew) { teacher_.starsNew = false; liveStars_.store(teacher_.stars); for (int l = 0; l < kNumLessons; ++l) liveBest_[l].store(teacher_.best[l]); }
        if (previewDoneFlag_) { previewDoneFlag_ = false; previewDone_.store(true); }
    }

    void parameterChanged(int index, float plainValue) override
    {
        if (index == kRescan && plainValue >= 0.5f) rescanRequested_.store(true);
        else if (index == kBrLoad && plainValue >= 0.5f) loadRequest_.store((int)std::lround(plainValue));
    }

    bool formatValue(int index, float plainValue, std::string& out) override
    {
        static const float ranges[3] = {8.0f, 16.0f, 50.0f};
        if (index == kPitch || index == kBPitch)
        {
            const float pct = plainValue * 0.01f * ranges[mpc::clamp(getInt(index == kPitch ? kPitchRange : kBPitchRange), 0, 2)];
            out = fmt("%+.2f%%", pct); return true;
        }
        if (index == kStripRange) { out = fmt("%.0f deg", plainValue); return true; }
        if (index == kPlay || index == kBPlay) { out = plainValue >= 0.5f ? "PLAY" : "STOP"; return true; }
        if (index == kFader || index == kBFader) { out = plainValue >= 0.5f ? "ON" : "OFF"; return true; }
        if (index == kXFader)
        {
            if (plainValue < 1.0f) out = "A"; else if (plainValue > 99.0f) out = "B";
            else out = fmt("A %.0f", 100.0 - plainValue) + fmt(" : %.0f B", plainValue);
            return true;
        }
        if (index == kXCurve)
        {
            out = plainValue < 20.0f ? "SMOOTH " : plainValue < 60.0f ? "MEDIUM " : plainValue < 90.0f ? "SHARP " : "RAZOR ";
            out += fmt("%.0f", plainValue); return true;
        }
        if (index == kHBpm) { out = fmt("%.0f BPM", plainValue); return true; }
        if (index == kHGhost || index == kHBeat || index == kHStars) return false;

        std::lock_guard<std::mutex> lk(textMutex_);
        if (index == kAName || index == kBName)
        {
            const int d = index == kAName ? 0 : 1;
            const int s = liveSlot_[d].load();
            out = std::string(d ? "B" : "A") + " " + std::to_string(s + 1) + "  " + slotName_[d][s];
            return true;
        }
        if (index >= kANames && index < kANames + 2 * kSlots)
        {
            const int k = index - kANames;
            out = slotName_[k / kSlots][k % kSlots];
            return true;
        }
        if (index == kBrFolder || index == kBrFolderName)
        {
            const int f = getInt(kBrFolder) - 1;
            if (scanning_.load()) out = "SUCHE SAMPLES ...";
            else if (f >= 0 && f < (int)browser_.folders.size())
            {
                out = browser_.folders[(size_t)f].label;
                if (out.size() > 31) out = "..." + out.substr(out.size() - 28);
            }
            else out = "-";
            return true;
        }
        if (index == kBrFile || (index >= kBrRows && index < kBrRows + 5))
        {
            const int f = getInt(kBrFolder) - 1;
            const int sel = getInt(kBrFile) - 1 + (index == kBrFile ? 0 : index - kBrRows - 2);
            out = "";
            if (!scanning_.load() && f >= 0 && f < (int)browser_.folders.size())
            {
                const BrowserFolder& bf = browser_.folders[(size_t)f];
                if (sel >= 0 && sel < (int)bf.files.size()) out = displayName(bf.files[(size_t)sel], 29);
            }
            if (index == kBrRows + 2 && !out.empty()) out = "> " + out;
            return true;
        }
        if (index == kBrInfo)
        {
            if (scanning_.load()) { out = "LAUFWERKE WERDEN DURCHSUCHT ..."; return true; }
            const int f = getInt(kBrFolder) - 1;
            const int nf = (int)browser_.folders.size();
            const int files = (f >= 0 && f < nf) ? (int)browser_.folders[(size_t)f].files.size() : 0;
            out = "DATEI " + std::to_string(std::min(getInt(kBrFile), files)) + "/" + std::to_string(files) +
                  "  ORDNER " + std::to_string(std::min(f + 1, nf)) + "/" + std::to_string(nf);
            return true;
        }
        if (index == kHMsg) { out = kMsgText[mpc::clamp(liveMsg_.load(), 0, kNumMsgs - 1)]; return true; }
        if (index == kHText1 || index == kHText2)
        {
            const Lesson& L = kLessons[mpc::clamp(getInt(kHLesson), 0, kNumLessons - 1)];
            out = index == kHText1 ? L.line1 : L.line2; return true;
        }
        if (index == kHScore)
        {
            const int l = mpc::clamp(getInt(kHLesson), 0, kNumLessons - 1);
            const int best = liveBest_[l].load();
            const int sc = liveScore_.load();
            std::string stars;
            for (int i = 0; i < 3; ++i) stars += i < best ? "*" : "-";
            out = "TREFFER " + std::to_string(sc % 1000) + "%   BESTE " + stars;
            return true;
        }
        return false;
    }

    // state: slot files and cues of both decks, teacher stars
    void saveExtraState(std::vector<uint8_t>& out) override
    {
        auto putD = [&out](double d) { uint8_t b[8]; std::memcpy(b, &d, 8); out.insert(out.end(), b, b + 8); };
        out.push_back('S'); out.push_back('K'); out.push_back(3);
        std::lock_guard<std::mutex> lk(wantMutex_);
        for (int d = 0; d < 2; ++d)
            for (int s = 0; s < kSlots; ++s)
            {
                std::string p = want_[d][s];
                if (!builtInDir_.empty() && p.compare(0, builtInDir_.size(), builtInDir_) == 0) p = "@" + p.substr(builtInDir_.size());
                const size_t n = std::min<size_t>(p.size(), 4000);
                out.push_back((uint8_t)(n & 255)); out.push_back((uint8_t)(n >> 8));
                out.insert(out.end(), p.begin(), p.begin() + (long)n);
                putD(deck_[d].cue[s]);
            }
        for (int l = 0; l < kNumLessons; ++l) out.push_back((uint8_t)liveBest_[l].load());
    }

    void loadExtraState(const uint8_t* data, size_t size) override
    {
        if (size < 3 || data[0] != 'S' || data[1] != 'K' || data[2] != 3) return;   // 1.0 states: keep the defaults
        size_t p = 3;
        std::string paths[2][kSlots];
        for (int d = 0; d < 2; ++d)
            for (int s = 0; s < kSlots; ++s)
            {
                if (p + 2 > size) return;
                const size_t n = (size_t)data[p] | ((size_t)data[p + 1] << 8); p += 2;
                if (p + n + 8 > size) return;
                std::string path((const char*)data + p, n); p += n;
                if (!path.empty() && path[0] == '@') path = builtInDir_ + path.substr(1);
                paths[d][s] = path;
                double c; std::memcpy(&c, data + p, 8); p += 8;
                cueStaging_[d][s] = std::isfinite(c) ? c : 0.0;
            }
        {
            std::lock_guard<std::mutex> lk(wantMutex_);
            for (int d = 0; d < 2; ++d) for (int s = 0; s < kSlots; ++s) want_[d][s] = paths[d][s];
        }
        for (int l = 0; l < kNumLessons && p < size; ++l) { const int b = mpc::clamp((int)data[p++], 0, 3); liveBest_[l].store(b); teacher_.best[l] = b; }
        cueStagingValid_.store(true);
    }

private:
    // ---------------------------------------------------------------------------------------------------------
    struct Deck
    {
        Record* slot[kSlots] = {};
        double cue[kSlots] = {};
        int cur = 0;
        // motion
        double x = 0.0, vel = 0.0, motorTarget = 0.0, startStep = 0.0, brakeStep = 0.0, catchCoef = 0.01;
        bool catching = false, motorOn = false;
        // hand follower
        bool handActive = false;
        double handTarget = 0.0, handVel = 0.0, rawTarget = 0.0, interpStep = 0.0;
        int interpLeft = 0;
        double springK = 0.0, springD = 0.0, unity = 1.0, samplesPerRev = 79380.0, stripScale = 1.0;
        bool loop = false;
        // jump cross-fade (cue, slot change)
        float xfade = 0.0f; double xOld = 0.0; const Record* xOldRec = nullptr;
        // gains
        float cutGain = 1.0f, gain = 1.0f, gainTarget = 1.0f, audible = 1.0f, audibleTarget = 1.0f;
        // style
        int style = 0;
        double wowPh = 0.0, flutPh = 0.0, wowNow = 0.0, wowStep = 0.0;
        float lpCoef = 1.0f, lpL = 0.0f, lpR = 0.0f, lp2L = 0.0f, lp2R = 0.0f, rumble = 0.0f, rum1 = 0.0f, rum2 = 0.0f, dust = 0.0f;
        float popEnv = 0.0f;
        uint32_t rng = 0x2545F491u;
    };

    enum Source { kSrcNone = 0, kSrcPitchBend, kSrcModWheel, kSrcScratch, kSrcJog, kSrcPad, kSrcHelper };

    // ---------------------------------------------------------------------------------------------------------
    void buildPrograms()
    {
        auto base = [this]() { std::vector<float> v((size_t)numParams()); for (int i = 0; i < numParams(); ++i) v[(size_t)i] = param(i).def; return v; };
        auto lesson = [](std::vector<float>& v, int l) { v[kHLesson] = (float)l; v[kHBpm] = kLessons[l].bpm; v[kCutMode] = kLessons[l].openMode ? 1.0f : 0.0f; };
        std::vector<float> v = base();
        addProgram("INIT", v);
        v = base(); lesson(v, 0); v[kSmooth] = 3.0f; v[kStripRange] = 180.0f; v[kXCurve] = 40.0f;
        addProgram("BABY SCRATCH", v);
        v = base(); lesson(v, 1); v[kStripRange] = 120.0f; v[kSmooth] = 6.0f;
        addProgram("DRAG", v);
        v = base(); lesson(v, 2); v[kCurve] = 0;
        addProgram("FORWARD", v);
        v = base(); lesson(v, 3); v[kCurve] = 0; v[kSmooth] = 1.8f; v[kStripRange] = 200.0f;
        addProgram("CHIRP", v);
        v = base(); lesson(v, 4); v[kCurve] = 0; v[kSmooth] = 2.5f; v[kStripRange] = 140.0f;
        addProgram("TRANSFORMER", v);
        v = base(); lesson(v, 5); v[kSmooth] = 2.0f; v[kStripRange] = 220.0f;
        addProgram("TEAR", v);
        v = base(); v[kMode] = 1; v[kAStyle] = 1; v[kBStyle] = 1; v[kStart] = 40.0f; v[kBrake] = 40.0f; v[kCatch] = 25.0f; v[kSmooth] = 1.0f; v[kXCurve] = 100.0f; v[kXLag] = 0.5f;
        addProgram("BATTLE TIGHT", v);
        v = base(); v[kMode] = 1; v[kSpeed] = 1; v[kBSpeed] = 1; v[kStripRange] = 270.0f; v[kSmooth] = 2.0f;
        addProgram("45 HYPE", v);
        v = base(); v[kMode] = 1; v[kAStyle] = 2; v[kBStyle] = 2; v[kCrackle] = 30.0f; v[kCurve] = 2; v[kSmooth] = 4.0f; v[kXCurve] = 30.0f;
        addProgram("DUSTY BELT", v);
    }

    // ---------------------------------------------------------------------------------------------------------
    // freshly loaded samples go into their slots at the start of a block
    void swapIn()
    {
        for (int d = 0; d < 2; ++d)
            for (int s = 0; s < kSlots; ++s)
                if (Record* fresh = pending_[d][s].exchange(nullptr))
                {
                    Deck& D = deck_[d];
                    Record* old = D.slot[s];
                    D.slot[s] = fresh;
                    if (D.xOldRec == old) { D.xOldRec = nullptr; D.xfade = 0.0f; }
                    if (old != nullptr) { Record* prev = retired_[d][s].exchange(old); delete prev; /* never: worker waits */ }
                    D.cue[s] = 0.0;
                    if (D.cur == s) placeAt(D, 0.0);
                }
        if (Record* p = previewPending_.exchange(nullptr))
        {
            Record* old = preview_;
            preview_ = p; previewPos_ = 0.0; previewPlaying_ = true;
            if (old != nullptr) { Record* prev = previewRetired_.exchange(old); delete prev; }
        }
    }

    void placeAt(Deck& D, double pos)
    {
        const double shift = pos - D.x;
        D.x = pos; D.handTarget += shift; D.rawTarget += shift;
        if (&D == &deck_[activeDeck_]) anchorPos_ += shift;
    }

    void readBlockParams(int frames)
    {
        static const float ranges[3] = {0.08f, 0.16f, 0.50f};
        // the explicit deck choice moves the hand (and the screen view) to the other deck
        const int want = mpc::clamp(getInt(kDeck), 0, 1);
        if (want != activeDeck_)
        {
            Deck& old = deck_[activeDeck_];
            if (old.handActive) letGo(old);
            padHold_ = false; releasePending_ = 0; handSrc_ = kSrcNone; anchorSrc_ = kSrcNone;
            activeDeck_ = want;
        }

        const double tauBase = get(kSmooth) * 0.001 * sr_;
        const double catchBase = get(kCatch) * 0.001 * sr_;
        const float xf = get(kXFader) * 0.01f, xc = get(kXCurve) * 0.01f, lag = get(kXLag) * 0.01f;
        const bool ham = getBool(kHamster);
        static const float cutMs[3] = {0.7f, 3.0f, 12.0f};
        cutStep_ = 1.0f / std::max(1.0f, cutMs[mpc::clamp(getInt(kCurve), 0, 2)] * 0.001f * (float)sr_);
        cutOpenMode_ = getInt(kCutMode) == 1;
        fireMode_ = getInt(kFireMode);

        for (int d = 0; d < 2; ++d)
        {
            Deck& D = deck_[d];
            const DeckParams& P = deckP_[d];
            // slot chosen on the screen (or by a pad, which also sets the parameter)
            const int s = mpc::clamp(getInt(P.slot), 0, kSlots - 1);
            if (s != D.cur) fire(d, s, false);

            D.style = mpc::clamp(getInt(P.style), 0, kNumStyles - 1);
            const Style& St = kStyles[D.style];
            const Record* r = D.slot[D.cur];
            const double fileSr = r != nullptr ? r->sampleRate : sr_;
            D.unity = fileSr / sr_;
            const double speedRatio = getInt(P.speed) == 1 ? 1.35 : 1.0;
            const double pitch = get(P.pitch) * 0.01 * ranges[mpc::clamp(getInt(P.prange), 0, 2)];
            const double dir = getBool(P.reverse) ? -1.0 : 1.0;
            D.motorOn = getBool(P.play);
            D.motorTarget = D.motorOn ? dir * speedRatio * (1.0 + pitch) * D.unity : 0.0;
            D.startStep = D.unity * speedRatio / std::max(1.0, get(P.start) * 0.001 * sr_ * St.torque);
            D.brakeStep = D.unity * speedRatio / std::max(1.0, get(P.brake) * 0.001 * sr_ * St.brake);
            D.catchCoef = 1.0 - std::exp(-1.0 / std::max(1.0, catchBase * St.catchMul));
            const double tau = std::max(8.0, tauBase * St.mass);
            D.springK = 1.0 / (tau * tau);
            D.springD = 2.0 / tau;
            D.samplesPerRev = fileSr / kRevPerSecond33;
            D.stripScale = (get(kStripRange) / 360.0) * D.samplesPerRev * 0.5 * (getInt(kStripDir) == 1 ? -1.0 : 1.0);
            D.loop = getBool(P.loop);

            // wow & flutter: evaluated at block edges, linear in between (no per-sample sin)
            const double secs = frames / sr_;
            const double w0 = D.wowNow;
            D.wowPh += St.wowHz * secs; D.wowPh -= std::floor(D.wowPh);
            D.flutPh += St.flutterHz * secs; D.flutPh -= std::floor(D.flutPh);
            const double w1 = St.wow * std::sin(2.0 * kPi * D.wowPh) + St.flutter * std::sin(2.0 * kPi * D.flutPh);
            D.wowNow = w0; D.wowStep = (w1 - w0) / std::max(1, frames);
            D.lpCoef = St.lpHz > 0.0f ? (float)(1.0 - std::exp(-2.0 * kPi * St.lpHz / sr_)) : 1.0f;
            D.rumble = St.rumble;
            D.dust = St.dust;

            // crossfader: x = how far the fader is open towards this deck (0 = closed end)
            float open = d == 0 ? 1.0f - xf : xf;
            if (ham) open = 1.0f - open;
            const float xg = xfShape(open, xc, lag);
            const float chan = getBool(P.chan) ? 1.0f : 0.0f;
            D.audibleTarget = chan * xg;
            D.gainTarget = chan * xg * mpc::dsp::dbToGain(get(P.vol));
        }
        levelTarget_ = mpc::dsp::dbToGain(get(kLevel));
        crackle_ = get(kCrackle) * 0.01f;
        timeoutRelease_ = getInt(kRelease) == 1;
        padBase_ = getInt(kPadBase) == 1 ? 37 : 36;

        // ---- the teacher ----
        teacher_.stepLen = sr_ * 60.0 / std::max(40.0f, get(kHBpm)) * 0.5;
        teacher_.click = getBool(kHClick);
        const int lesson = mpc::clamp(getInt(kHLesson), 0, kNumLessons - 1);
        const bool wantDemo = getBool(kHDemo), wantRun = getBool(kHRun);
        if (wantDemo && !prevDemo_) { setFromAudio(kHRun, 0.0f); startLesson(lesson, true); }
        else if (wantRun && !prevRun_) { setFromAudio(kHDemo, 0.0f); startLesson(lesson, false); }
        else if (!wantDemo && !wantRun && teacher_.running) stopLesson();
        else if (teacher_.running && lesson != teacher_.lesson) startLesson(lesson, teacher_.demo);
        prevDemo_ = getBool(kHDemo); prevRun_ = getBool(kHRun);
        // the demo plays two bars, then it is your turn
        if (teacher_.running && teacher_.demo && teacher_.bar >= 2)
        {
            setFromAudio(kHDemo, 0.0f); setFromAudio(kHRun, 1.0f); prevDemo_ = false; prevRun_ = true;
            startLesson(lesson, false);
        }
        if (teacher_.running && teacher_.demo) stripEvent(teacher_.ghost, kSrcHelper);
    }

    // 0..1 open travel -> gain. curve 0: constant power over the whole travel; 1: open after 1.5 %.
    static float xfShape(float x, float curve, float lag)
    {
        if (x <= lag) return 0.0f;
        const float u = (x - lag) / std::max(1e-4f, 1.0f - lag);
        const float w = 1.0f - 0.985f * std::pow(mpc::clamp(curve, 0.0f, 1.0f), 0.6f);
        const float v = std::min(1.0f, u / std::max(0.01f, w));
        return std::sin(1.5707963f * v);
    }

    void setFromAudio(int index, float plain)
    {
        set(index, plain);
        dirty_[index >> 6].fetch_or(1ull << (index & 63));
    }

    void startLesson(int lesson, bool demo)
    {
        Deck& D = deck_[activeDeck_];
        if (D.handActive && handSrc_ == kSrcHelper) letGo(D);
        teacher_.demo = demo;
        teacher_.start(lesson);
        // the teacher sets the deck up: motor off, cut pad as the lesson needs it, crossfader open to this deck
        if (getBool(deckP_[activeDeck_].play)) setFromAudio(deckP_[activeDeck_].play, 0.0f);
        setFromAudio(kCutMode, kLessons[lesson].openMode ? 1.0f : 0.0f);
        float open = activeDeck_ == 0 ? 1.0f - get(kXFader) * 0.01f : get(kXFader) * 0.01f;
        if (getBool(kHamster)) open = 1.0f - open;
        if (xfShape(open, get(kXCurve) * 0.01f, get(kXLag) * 0.01f) < 0.5f)
            setFromAudio(kXFader, (activeDeck_ == 0) != getBool(kHamster) ? 0.0f : 100.0f);
        if (!getBool(deckP_[activeDeck_].chan)) setFromAudio(deckP_[activeDeck_].chan, 1.0f);
    }

    void stopLesson()
    {
        Deck& D = deck_[activeDeck_];
        if (D.handActive && handSrc_ == kSrcHelper) letGo(D);
        teacher_.stop();
    }

    // a slot goes on the platter at its cue (from a pad or the slot buttons)
    void fire(int d, int s, bool fromPad)
    {
        Deck& D = deck_[d];
        if (fromPad && getInt(deckP_[d].slot) != s) setFromAudio(deckP_[d].slot, (float)s);
        const Record* old = D.slot[D.cur];
        if (old != nullptr) { D.xOldRec = old; D.xOld = D.x; D.xfade = 1.0f; }
        D.cur = s;
        if (D.handActive) letGo(D);
        placeAt(D, D.cue[s]);
        if (fireMode_ == 1)
        {
            if (!getBool(deckP_[d].play)) setFromAudio(deckP_[d].play, 1.0f);
            const double speedRatio = getInt(deckP_[d].speed) == 1 ? 1.35 : 1.0;
            D.vel = (getBool(deckP_[d].reverse) ? -1.0 : 1.0) * speedRatio * D.unity;   // needle drop on a spinning record
            D.catching = false;
        }
    }

    // the SCRATCH parameter (strip in Q-LINK mode, a Q-Link knob) and the on-screen record move the hand too
    void pollParamHands(int frames)
    {
        const float s = get(kScratch);
        if (std::fabs(s - lastScratch_) > 1e-6f) { lastScratch_ = s; stripEvent((double)s * 0.02 - 1.0, kSrcScratch); }
        const float j = get(kJog);
        if (std::fabs(j - lastJog_) > 1e-6f)
        {
            double dlt = (double)(j - lastJog_) / 360.0;
            if (dlt > 0.5) dlt -= 1.0; else if (dlt < -0.5) dlt += 1.0;
            lastJog_ = j;
            jogEvent(dlt);
        }
        Deck& D = deck_[activeDeck_];
        if (D.handActive && !padHold_ && handSrc_ != kSrcHelper)
        {
            idleSamples_ += frames;
            const bool timeoutSource = handSrc_ != kSrcPitchBend || timeoutRelease_;
            if (timeoutSource && idleSamples_ > (int)(0.120 * sr_)) letGo(D);
        }
    }

    void grab(Source src)
    {
        Deck& D = deck_[activeDeck_];
        if (!D.handActive)
        {
            D.handActive = true;
            D.handTarget = D.rawTarget = D.x;
            D.interpLeft = 0;
            lastEventClock_ = -1.0e12;
            D.handVel = D.vel;                  // the hand meets the record at its current speed: no click
        }
        handSrc_ = src;
        idleSamples_ = 0;
        releasePending_ = 0;
    }

    void letGo(Deck& D)
    {
        D.handActive = false;
        D.vel = D.handVel;                      // the record keeps the speed the hand gave it
        D.catching = D.motorTarget != 0.0;      // ... the running motor grabs it with the CATCH time
        if (&D == &deck_[activeDeck_]) { handSrc_ = kSrcNone; releasePending_ = 0; }
    }

    void stripEvent(double v, Source src)
    {
        Deck& D = deck_[activeDeck_];
        if (src != kSrcHelper && teacher_.running && teacher_.demo) return;   // the teacher has the record
        if (!D.handActive || handSrc_ != src || anchorSrc_ != src)
        {
            grab(src);
            anchorVal_ = v;
            anchorPos_ = D.rawTarget;
            anchorSrc_ = src;
        }
        moveTarget(D, anchorPos_ + (v - anchorVal_) * D.stripScale);
        idleSamples_ = 0;
        releasePending_ = 0;
        stripLedFrame_ = 1 + mpc::clamp((int)std::lround((v * 0.5 + 0.5) * (kStripFrames - 2)), 0, kStripFrames - 2);
    }

    void jogEvent(double turns)
    {
        Deck& D = deck_[activeDeck_];
        if (teacher_.running && teacher_.demo) return;
        if (!D.handActive || handSrc_ != kSrcJog) { grab(kSrcJog); anchorSrc_ = kSrcJog; }
        moveTarget(D, D.rawTarget + turns * D.samplesPerRev * (getInt(kStripDir) == 1 ? -1.0 : 1.0));
        idleSamples_ = 0;
        stripLedFrame_ = (kStripFrames - 1) / 2 + 1;
    }

    // Controllers report every few ms in steps; the target glides to each new value over the measured report
    // interval, and the spring smooths what is left.
    void moveTarget(Deck& D, double raw)
    {
        const double now = eventClock_;
        const double dt = now - lastEventClock_;
        lastEventClock_ = now;
        if (dt > 0.0 && dt < 0.025 * sr_)
            eventInterval_ += (mpc::clamp(dt, 0.0003 * sr_, 0.012 * sr_) - eventInterval_) * 0.3;
        D.rawTarget = raw;
        const double glide = (dt > 0.0 && dt < 0.025 * sr_) ? std::max(1.0, eventInterval_) : 1.0;
        D.interpLeft = (int)std::lround(glide);
        D.interpStep = (D.rawTarget - D.handTarget) / (double)D.interpLeft;
    }

    void handleMidi(const mpc::MidiEvent& ev)
    {
        Deck& D = deck_[activeDeck_];
        if (ev.isPitchBend())
        {
            const int pb = ev.pitchBend();
            if (pb == 0)
            {
                if (D.handActive && handSrc_ == kSrcPitchBend && !timeoutRelease_) releasePending_ = (int)(0.025 * sr_);
                return;
            }
            stripEvent((double)pb / 8192.0, kSrcPitchBend);
        }
        else if (ev.isController())
        {
            if (ev.controller() == 1)       { mwMsb_ = ev.controllerValue(); mwLsb_ = 0; stripEvent(mwValue(), kSrcModWheel); }
            else if (ev.controller() == 33) { mwLsb_ = ev.controllerValue(); if (handSrc_ == kSrcModWheel) stripEvent(mwValue(), kSrcModWheel); }
            else if (ev.controller() == 120 || ev.controller() == 123)
            {
                cutHeld_ = false; padHold_ = false; setCueHeld_ = false;
                for (Deck& X : deck_) if (X.handActive) letGo(X);
            }
        }
        else if (ev.isNoteOn() || ev.isNoteOff())
        {
            const int f = (((ev.note() - padBase_) % 16) + 16) % 16;
            handlePad(f, ev.isNoteOn());
        }
    }

    double mwValue() const { return ((double)((mwMsb_ << 7) | mwLsb_) / 16383.0) * 2.0 - 1.0; }

    void handlePad(int f, bool on)
    {
        const int d = activeDeck_;
        Deck& D = deck_[d];
        const DeckParams& P = deckP_[d];
        if (f < kSlots) { if (on) fire(d, f, true); return; }
        switch (f)
        {
            case 8:  if (on) setFromAudio(P.play, getBool(P.play) ? 0.0f : 1.0f); break;
            case 9:  if (on) { cutHeld_ = true; cutDeck_ = d; } else cutHeld_ = false; break;
            case 10:
                if (on) { padHold_ = true; grab(kSrcPad); anchorSrc_ = kSrcPad; D.rawTarget = D.handTarget = D.x; D.interpLeft = 0; }
                else { padHold_ = false; if (D.handActive && handSrc_ == kSrcPad) letGo(D); }
                break;
            case 11: if (on) setFromAudio(kDeck, d == 0 ? 1.0f : 0.0f); break;   // takes effect at the next block
            case 12: if (on) jumpTo(D, D.cue[D.cur]); break;
            case 13: if (on) D.cue[D.cur] = D.x; break;
            case 14: if (on) setFromAudio(P.reverse, getBool(P.reverse) ? 0.0f : 1.0f); break;
            case 15: if (on) setFromAudio(P.speed, getInt(P.speed) == 1 ? 0.0f : 1.0f); break;
            default: break;
        }
        readLater_ = true;
    }

    void jumpTo(Deck& D, double pos)
    {
        const Record* r = D.slot[D.cur];
        if (r != nullptr) { D.xOldRec = r; D.xOld = D.x; D.xfade = 1.0f; }
        placeAt(D, pos);
    }

    // ---------------------------------------------------------------------------------------------------------
    void render(mpc::ProcessContext& ctx, int from, int to)
    {
        if (readLater_) { readLater_ = false; refreshMotors(); }
        float* L = ctx.outputs[0];
        float* R = ctx.numOutputs > 1 ? ctx.outputs[1] : nullptr;
        const float xfadeStep = 1.0f / std::max(1.0f, 0.003f * (float)sr_);
        const float gainCoef = 1.0f - std::exp(-1.0f / (0.0004f * (float)sr_));   // 0.4 ms: smooth but instant
        Deck& act = deck_[activeDeck_];

        for (int i = from; i < to; ++i)
        {
            if (releasePending_ > 0 && --releasePending_ == 0) letGo(act);
            float outL = 0.0f, outR = 0.0f;
            for (int d = 0; d < 2; ++d)
            {
                Deck& D = deck_[d];
                stepDeck(D);
                // CUT pad / teacher demo
                float cutTarget = 1.0f;
                if (teacher_.running && teacher_.demo && d == activeDeck_) cutTarget = teacher_.faderTarget ? 1.0f : 0.0f;
                else if (cutOpenMode_ && d == activeDeck_) cutTarget = (cutHeld_ && cutDeck_ == d) ? 1.0f : 0.0f;
                else if (cutHeld_ && cutDeck_ == d) cutTarget = 0.0f;
                if (D.cutGain < cutTarget) D.cutGain = std::min(cutTarget, D.cutGain + cutStep_);
                else if (D.cutGain > cutTarget) D.cutGain = std::max(cutTarget, D.cutGain - cutStep_);
                D.gain += (D.gainTarget - D.gain) * gainCoef;
                D.audible += (D.audibleTarget - D.audible) * gainCoef;
                const float g = D.gain * D.cutGain;
                if (g < 1e-6f) { D.xfade = 0.0f; D.xOldRec = nullptr; continue; }   // closed: nothing to hear
                float sl = 0.0f, sr = 0.0f;
                readDeck(D, sl, sr, xfadeStep);
                outL += sl * g; outR += sr * g;
            }

            // teacher: watches the active deck, ticks the click
            if (teacher_.running)
            {
                const Record* r = act.slot[act.cur];
                const bool aud = act.audible * act.cutGain > 0.5f;
                const float c = teacher_.tick(act.x, act.handActive && handSrc_ != kSrcHelper, aud, act.motorOn, act.stripScale, r != nullptr, sr_);
                outL += c; outR += c;
            }

            // browser preview: plays the selected file once at normal speed
            if (previewPlaying_ && preview_ != nullptr)
            {
                if (!getBool(kBrPreview)) previewPlaying_ = false;
                else
                {
                    float pl, pr;
                    readLevel(*preview_, 0, previewPos_, false, pl, pr);
                    outL += pl * 0.8f; outR += pr * 0.8f;
                    previewPos_ += preview_->sampleRate / sr_;
                    if (previewPos_ >= (double)preview_->length) { previewPlaying_ = false; previewDoneFlag_ = true; }
                }
            }

            levelGain_ += (levelTarget_ - levelGain_) * 0.0015f;
            float ol = mpc::dsp::sanitize(outL * levelGain_), orr = mpc::dsp::sanitize(outR * levelGain_);
            if (std::fabs(ol) < 1e-20f) ol = 0.0f;
            if (std::fabs(orr) < 1e-20f) orr = 0.0f;
            L[i] = ol;
            if (R) R[i] = orr;
        }
    }

    void refreshMotors()
    {
        static const float ranges[3] = {0.08f, 0.16f, 0.50f};
        for (int d = 0; d < 2; ++d)
        {
            Deck& D = deck_[d];
            const DeckParams& P = deckP_[d];
            const double speedRatio = getInt(P.speed) == 1 ? 1.35 : 1.0;
            const double pitch = get(P.pitch) * 0.01 * ranges[mpc::clamp(getInt(P.prange), 0, 2)];
            D.motorOn = getBool(P.play);
            D.motorTarget = D.motorOn ? (getBool(P.reverse) ? -1.0 : 1.0) * speedRatio * (1.0 + pitch) * D.unity : 0.0;
        }
    }

    // hand or motor moves the record one output sample
    void stepDeck(Deck& D)
    {
        if (D.handActive)
        {
            if (D.interpLeft > 0) { D.handTarget += D.interpStep; if (--D.interpLeft == 0) D.handTarget = D.rawTarget; }
            const double a = D.springK * (D.handTarget - D.x) - D.springD * D.handVel;
            D.handVel += a;
            if (D.handVel > kMaxSpeed) D.handVel = kMaxSpeed; else if (D.handVel < -kMaxSpeed) D.handVel = -kMaxSpeed;
            D.x += D.handVel;
            D.vel = D.handVel;
        }
        else
        {
            const double target = D.motorTarget * (1.0 + D.wowNow);
            if (D.catching)
            {
                D.vel += (target - D.vel) * D.catchCoef;
                if (std::fabs(target - D.vel) < 0.002 * D.unity) { D.vel = target; D.catching = false; }
            }
            else if (D.vel != target)
            {
                const bool speedingUp = std::fabs(target) > std::fabs(D.vel) && (target * D.vel >= 0.0);
                const double step = speedingUp ? D.startStep : D.brakeStep;
                // the wow wobble is followed directly; only real speed changes ramp
                if (std::fabs(target - D.vel) < 0.01 * D.unity) D.vel = target;
                else if (D.vel < target) D.vel = std::min(target, D.vel + step);
                else D.vel = std::max(target, D.vel - step);
            }
            D.x += D.vel;
            D.handVel = D.vel;
        }
        D.wowNow += D.wowStep;
    }

    void readDeck(Deck& D, float& sl, float& sr, float xfadeStep)
    {
        const Record* rec = D.slot[D.cur];
        const double speed = std::fabs(D.vel);
        if (rec != nullptr) readAt(*rec, D.x, speed, D.loop, sl, sr);
        if (D.xfade > 0.0f)
        {
            float ol = 0.0f, orr = 0.0f;
            D.xOld += D.vel;
            if (D.xOldRec != nullptr) readAt(*D.xOldRec, D.xOld, speed, D.loop, ol, orr);
            sl += (ol - sl) * D.xfade; sr += (orr - sr) * D.xfade;
            D.xfade = std::max(0.0f, D.xfade - xfadeStep);
            if (D.xfade <= 0.0f) D.xOldRec = nullptr;
        }
        // style tone: belt-drive cartridge is warmer (two one-poles), bearing rumble while the platter turns
        if (D.lpCoef < 1.0f)
        {
            D.lpL += (sl - D.lpL) * D.lpCoef; D.lpR += (sr - D.lpR) * D.lpCoef;
            D.lp2L += (D.lpL - D.lp2L) * D.lpCoef; D.lp2R += (D.lpR - D.lp2R) * D.lpCoef;
            sl = D.lp2L; sr = D.lp2R;
        }
        const float motion = (float)std::min(1.0, speed / std::max(1e-6, D.unity));
        if (D.rumble > 0.0f && motion > 0.01f)
        {
            D.rng = D.rng * 1664525u + 1013904223u;
            const float n = ((float)(D.rng >> 8) * (1.0f / 8388608.0f)) - 1.0f;
            D.rum1 += (n - D.rum1) * 0.004f; D.rum2 += (D.rum1 - D.rum2) * 0.004f;
            const float r = D.rum2 * 40.0f * D.rumble * motion;
            sl += r; sr += r;
        }
        // crackle: dust pops, louder when the record moves
        const float cr = std::min(1.0f, crackle_ + D.dust);
        if (cr > 0.0f)
        {
            D.rng = D.rng * 1664525u + 1013904223u;
            const float u = (float)(D.rng >> 8) * (1.0f / 16777216.0f);
            if (u < cr * 0.0006f * motion) D.popEnv = (0.15f + u * 400.0f) * cr;
            D.rng = D.rng * 1664525u + 1013904223u;
            const float n = ((float)(D.rng >> 8) * (1.0f / 8388608.0f)) - 1.0f;
            const float c = n * (D.popEnv + 0.004f * cr * motion);
            D.popEnv *= 0.86f;
            sl += c; sr += c;
        }
    }

    // band-limited read: pick the mip level for the speed, cross-fade between two levels
    static void readAt(const Record& r, double pos, double speed, bool loop, float& outL, float& outR)
    {
        // Level k holds content up to about 9.9 kHz / 2^(k-1). Keep every fold above ~15 kHz.
        double lvl;
        if (speed <= 1.0) lvl = 0.0;
        else if (speed <= 1.45) lvl = (speed - 1.0) * (0.986 / 0.45);
        else lvl = std::log2(speed) + 0.45;
        float aL, aR;
        if (lvl >= kMipLevels - 1) { readLevel(r, kMipLevels - 1, pos, loop, outL, outR); return; }
        const int L0 = (int)lvl;
        const float t = (float)(lvl - L0);
        readLevel(r, L0, pos, loop, aL, aR);
        if (t > 0.001f) { float bL, bR; readLevel(r, L0 + 1, pos, loop, bL, bR); aL += (bL - aL) * t; aR += (bR - aR) * t; }
        outL = aL; outR = aR;
    }

    static void readLevel(const Record& r, int level, double pos0, bool loop, float& outL, float& outR)
    {
        const size_t n = r.len[level];
        double p = pos0 / (double)(1u << level);
        const double total = (double)n;
        if (loop) { p = std::fmod(p, total); if (p < 0.0) p += total; }
        else if (p < -2.0 || p >= total + 2.0) { outL = outR = 0.0f; return; }
        const double fl = std::floor(p);
        const long i0 = (long)fl;
        const float t = (float)(p - fl);
        auto at = [&](const std::vector<float>& v, long i) -> float
        {
            if (loop) { i %= (long)n; if (i < 0) i += (long)n; return v[(size_t)i]; }
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
    // background thread
    void loadWantedSlots(bool all)
    {
        for (int d = 0; d < 2; ++d)
            for (int s = 0; s < kSlots; ++s)
            {
                std::string want;
                { std::lock_guard<std::mutex> lk(wantMutex_); want = want_[d][s]; }
                if (want == loaded_[d][s]) continue;
                if (pending_[d][s].load() != nullptr || retired_[d][s].load() != nullptr) continue;
                loaded_[d][s] = want;
                Record* r = want.empty() ? nullptr : loadRecord(want);
                {
                    std::lock_guard<std::mutex> lk(textMutex_);
                    slotName_[d][s] = r != nullptr ? r->name : (want.empty() ? std::string("-") : "FEHLT: " + displayName(fileOf(want), 14));
                }
                if (r != nullptr) pending_[d][s].store(r);
                bump(deckP_[d].names + s); bump(deckP_[d].name);
                if (!all) return;   // one load per pass keeps the reporter responsive
            }
    }

    void bump(int index) { bumps_[index >> 6].fetch_or(1ull << (index & 63)); }

    std::string selectedPath()
    {
        std::lock_guard<std::mutex> lk(textMutex_);
        const int f = getInt(kBrFolder) - 1, i = getInt(kBrFile) - 1;
        if (f < 0 || f >= (int)browser_.folders.size()) return std::string();
        const BrowserFolder& bf = browser_.folders[(size_t)f];
        if (i < 0 || i >= (int)bf.files.size()) return std::string();
        return bf.path + "/" + bf.files[(size_t)i];
    }

    void rescan()
    {
        scanning_.store(true);
        for (int r = 0; r < 5; ++r) bump(kBrRows + r);
        bump(kBrInfo); bump(kBrFolderName);
        BrowserIndex idx;
        const std::string pf = mpc::pluginFolder();
        idx.scan(builtInDir_, pf.empty() ? std::string() : pf + "/My Samples");
        {
            std::lock_guard<std::mutex> lk(textMutex_);
            browser_ = std::move(idx);
        }
        scanning_.store(false);
        for (int r = 0; r < 5; ++r) bump(kBrRows + r);
        bump(kBrInfo); bump(kBrFolderName); bump(kBrFolder); bump(kBrFile);
    }

    void backgroundLoop()
    {
        int tick = 0;
        float lastAngle[2] = {-1.0f, -1.0f}, lastStrobe[2] = {-1.0f, -1.0f};
        int lastStrip = -1, lastCut[2] = {-1, -1}, lastActive = -1, lastSlot[2] = {-1, -1};
        int lastGhost = -1, lastBeat = -1, lastStars = -1, lastMsg = -1, lastScore = -1, lastFade = -1, lastLesson = -1;
        int lastFolder = -1, lastFile = -1;
        bool previewWasOn = false;
        std::string previewPath;
        const auto t0 = std::chrono::steady_clock::now();
        rescan();
        while (!stopThread_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(15));
            ++tick;

            for (int d = 0; d < 2; ++d) for (int s = 0; s < kSlots; ++s) delete retired_[d][s].exchange(nullptr);
            delete previewRetired_.exchange(nullptr);

            if (rescanRequested_.exchange(false))
            {
                rescan();
                if (getBool(kRescan)) { set(kRescan, 0.0f); if (effect_ && host_) notifyHostParameterChanged(kRescan); }
            }

            // browser: LOAD TO SLOT n puts the selected file into slot n of the active deck and onto its platter
            const int lr = loadRequest_.exchange(0);
            if (lr > 0)
            {
                const std::string p = selectedPath();
                const int d = mpc::clamp(getInt(kDeck), 0, 1), s = mpc::clamp(lr - 1, 0, kSlots - 1);
                if (!p.empty())
                {
                    { std::lock_guard<std::mutex> lk(wantMutex_); want_[d][s] = p; }
                    set(deckP_[d].slot, (float)s);
                    if (effect_ && host_) notifyHostParameterChanged(deckP_[d].slot);
                }
                set(kBrLoad, 0.0f);
                if (effect_ && host_) notifyHostParameterChanged(kBrLoad);
            }
            loadWantedSlots(false);

            // browser: a new folder starts at its first file; the rows follow the selection
            const int folder = getInt(kBrFolder), file = getInt(kBrFile);
            if (folder != lastFolder)
            {
                if (lastFolder >= 0 && file != 1) { set(kBrFile, 1.0f); if (effect_ && host_) notifyHostParameterChanged(kBrFile); }
                lastFolder = folder; lastFile = -1;
                bump(kBrFolderName); bump(kBrInfo);
            }
            if (getInt(kBrFile) != lastFile)
            {
                lastFile = getInt(kBrFile);
                for (int r = 0; r < 5; ++r) bump(kBrRows + r);
                bump(kBrInfo);
            }
            // preview: (re)load when switched on or when the selection changes while on
            const bool pv = getBool(kBrPreview);
            if (pv)
            {
                const std::string p = selectedPath();
                if ((!previewWasOn || p != previewPath) && previewPending_.load() == nullptr && previewRetired_.load() == nullptr)
                {
                    previewPath = p;
                    if (Record* r = p.empty() ? nullptr : loadRecord(p, 30.0)) previewPending_.store(r);
                }
            }
            else previewPath.clear();
            previewWasOn = pv;
            if (previewDone_.exchange(false) && getBool(kBrPreview))
            {
                set(kBrPreview, 0.0f); previewWasOn = false;
                if (effect_ && host_) notifyHostParameterChanged(kBrPreview);
            }

            // a new lesson starts at its own tempo
            const int lesson = getInt(kHLesson);
            if (lesson != lastLesson)
            {
                if (lastLesson >= 0) { set(kHBpm, kLessons[mpc::clamp(lesson, 0, kNumLessons - 1)].bpm); if (effect_ && host_) notifyHostParameterChanged(kHBpm); }
                lastLesson = lesson;
                bump(kHText1); bump(kHText2); bump(kHScore);
            }

            if (effect_ == nullptr || host_ == nullptr) continue;

            // ~33 Hz live display
            if ((tick & 1) == 0)
            {
                const int active = liveActive_.load();
                const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
                if (active != lastActive) { lastActive = active; lastAngle[active] = -1.0f; lastStrobe[active] = -1.0f; }
                for (int d = 0; d < 2; ++d)
                {
                    const DeckParams& P = deckP_[d];
                    const double revs = liveRevs_[d].load();
                    // only the deck on screen turns (half the traffic); the other one catches up when shown
                    if (d == active)
                    {
                        const float a = (float)(revs - std::floor(revs));
                        float da = std::fabs(a - lastAngle[d]); if (da > 0.5f) da = 1.0f - da;
                        if (lastAngle[d] < 0.0f || da >= 0.5f / kAngleFrames) { lastAngle[d] = a; setNormalised(P.angle, a); notifyHostParameterChanged(P.angle); }
                        const double ph = revs * kStrobeDots - secs * 100.0;
                        const float sp = (float)(ph - std::floor(ph));
                        float ds = std::fabs(sp - lastStrobe[d]); if (ds > 0.5f) ds = 1.0f - ds;
                        if (lastStrobe[d] < 0.0f || ds >= 0.5f / kStrobeFrames) { lastStrobe[d] = sp; setNormalised(P.strobe, sp); notifyHostParameterChanged(P.strobe); }
                    }
                    const int c = liveCut_[d].load() ? 1 : 0;
                    if (c != lastCut[d]) { lastCut[d] = c; set(P.cutled, (float)c); notifyHostParameterChanged(P.cutled); }
                    const int sl = liveSlot_[d].load();
                    if (sl != lastSlot[d]) { lastSlot[d] = sl; bump(P.name); }
                }
                const int s = liveStrip_.load();
                if (s != lastStrip) { lastStrip = s; set(kStripLed, (float)s); notifyHostParameterChanged(kStripLed); }
                auto report = [&](int idx, int v, int& last) { if (v != last) { last = v; set(idx, (float)v); notifyHostParameterChanged(idx); } };
                report(kHGhost, liveGhost_.load(), lastGhost);
                report(kHBeat, liveBeat_.load(), lastBeat);
                report(kHStars, liveStars_.load(), lastStars);
                report(kHFadeLed, liveFadeLed_.load() ? 1 : 0, lastFade);
                const int m = liveMsg_.load();
                if (m != lastMsg) { lastMsg = m; bump(kHMsg); }
                const int sc = liveScore_.load();
                if (sc != lastScore) { lastScore = sc; bump(kHScore); }

                for (int w = 0; w < 2; ++w)
                {
                    const uint64_t dbits = dirty_[w].exchange(0ull);
                    for (int i = 0; i < 64; ++i) if (dbits & (1ull << i)) notifyHostParameterChanged(w * 64 + i);
                    const uint64_t bbits = bumps_[w].exchange(0ull);
                    for (int i = 0; i < 64; ++i)
                        if (bbits & (1ull << i))
                        {
                            const int idx = w * 64 + i;
                            float v = getNormalised(idx) + 0.0101f; if (v > 1.0f) v -= 1.0f;   // a new value: the MPC re-reads the text
                            setNormalised(idx, v);
                            notifyHostParameterChanged(idx);
                        }
                }
            }
            if (needDisplayUpdate_.exchange(false)) requestDisplayUpdate();
        }
    }

    // ---------------------------------------------------------------------------------------------------------
    double sr_ = 44100.0;
    Deck deck_[2];
    DeckParams deckP_[2];
    int activeDeck_ = 0;
    // hand (one hand, on the active deck)
    bool padHold_ = false;
    Source handSrc_ = kSrcNone, anchorSrc_ = kSrcNone;
    double anchorPos_ = 0.0, anchorVal_ = 0.0;
    double eventInterval_ = 88.0, lastEventClock_ = -1.0e12;
    double blockClock_ = 0.0, eventClock_ = 0.0;
    int releasePending_ = 0, idleSamples_ = 0, stripLedFrame_ = 0;
    bool timeoutRelease_ = false;
    float lastScratch_ = 50.0f, lastJog_ = 0.0f;
    int mwMsb_ = 64, mwLsb_ = 0;
    // pads, cut
    int padBase_ = 36, cutDeck_ = 0, fireMode_ = 1;
    bool cutHeld_ = false, setCueHeld_ = false, readLater_ = false, cutOpenMode_ = false;
    float cutStep_ = 0.03f;
    double cueStaging_[2][kSlots] = {};
    std::atomic<bool> cueStagingValid_{false};
    // output
    float levelGain_ = 0.7f, levelTarget_ = 0.7f, crackle_ = 0.0f;
    // teacher
    Teacher teacher_;
    bool prevDemo_ = false, prevRun_ = false;
    // preview
    Record* preview_ = nullptr;
    std::atomic<Record*> previewPending_{nullptr}, previewRetired_{nullptr};
    double previewPos_ = 0.0;
    bool previewPlaying_ = false, previewDoneFlag_ = false;
    std::atomic<bool> previewDone_{false};
    // records and threads
    std::atomic<Record*> pending_[2][kSlots] = {};    // worker -> audio
    std::atomic<Record*> retired_[2][kSlots] = {};    // audio -> worker (deleted there)
    std::mutex wantMutex_;                           // never taken on the audio thread
    std::string want_[2][kSlots], loaded_[2][kSlots];
    std::string builtInDir_;
    std::mutex textMutex_;                           // names, browser index (never on the audio thread)
    std::string slotName_[2][kSlots];
    BrowserIndex browser_;
    std::atomic<bool> scanning_{true};
    std::atomic<int> loadRequest_{0};
    std::atomic<bool> rescanRequested_{false}, needDisplayUpdate_{false}, stopThread_{false};
    std::thread worker_;
    bool threadStarted_ = false;
    // live display values (audio -> background reporter)
    std::atomic<double> liveRevs_[2] = {};
    std::atomic<bool> liveCut_[2] = {};
    std::atomic<int> liveSlot_[2] = {}, liveStrip_{0}, liveActive_{0}, liveGhost_{0}, liveBeat_{0}, liveStars_{0}, liveMsg_{0}, liveScore_{0};
    std::atomic<int> liveBest_[kNumLessons] = {};
    std::atomic<bool> liveFadeLed_{false};
    std::atomic<uint64_t> dirty_[2] = {}, bumps_[2] = {};
};

MPC_PLUGIN_ENTRY(SKRATCHA)
