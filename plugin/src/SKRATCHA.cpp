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
#include "skr_feed.h"
#include "skr_midimon.h"
#include "skr_helper.h"
#include "skr_seq.h"

#include <algorithm>
#include <dirent.h>
#include <unistd.h>
#include <sys/stat.h>
#include <cerrno>
#include <atomic>
#include <chrono>
#include <cstdlib>
#if defined(__linux__)
  #include <sys/resource.h>
  #include <sys/syscall.h>
  #include <unistd.h>
#endif
#include <cstring>
#include <ctime>
#include <cstdio>
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
constexpr int kMaxEntries = 4000;   // browser: entries per list
constexpr int kAngleFrames = 48;     // record film strip in the skin (one turn)
constexpr int kStrobeFrames = 8;
constexpr int kStrobeDots = 180;
constexpr int kStripFrames = 33;
constexpr int kNumStyles = 10;
constexpr float kMaxSpeed = 32.0f;

// ---- turntable styles: same controls, different machine -------------------------------------------------------
struct Style
{
    const char* name;
    float torque;      // x START time (lower = stronger motor)
    float brake;       // x BRAKE time
    float catchMul;    // x CATCH time (belt / spring motors catch late)
    float mass;        // x SMOOTH (heavier platter = more inertia under the hand)
    float wow, wowHz, flutter, flutterHz;   // speed wobble (fraction of speed)
    float lpHz, hpHz;  // tone: low pass (0 = off), high pass (0 = off)
    float peakHz, peakDb, peakQ;            // resonance of the horn / small speaker / cartridge
    float drive;       // saturation (tubes, horn)
    int   mono;        // old machines play mono
    float hiss;        // surface noise while the record turns
    float rumble;      // motor/bearing rumble level
    float dust;        // extra crackle
    float rpm;         // base speed of the platter (78 = shellac)
};
// ten machines from the gramophone to today: each one sounds, feels and looks different
const Style kStyles[kNumStyles] = {
//    name                     torq  brake catch mass   wow     Hz    flutter Hz     LP      HP     peakHz peakDb Q    drive mono hiss    rumble dust  rpm
    {"1912 GRAMMOPHON",        2.60f, 3.0f, 3.0f, 1.60f, 0.0080f, 0.8f, 0.0030f, 5.0f, 3500.f, 380.f, 1500.f, 7.0f, 1.2f, 0.45f, 1, 0.015f, 0.004f, 0.45f, 78.f},
    {"1935 SCHELLACK",         2.00f, 2.4f, 2.4f, 1.40f, 0.0040f, 0.6f, 0.0015f, 6.0f, 5000.f, 150.f, 2200.f, 4.0f, 0.9f, 0.25f, 1, 0.010f, 0.003f, 0.32f, 78.f},
    {"1955 ROEHRENTRUHE",      2.40f, 2.6f, 2.6f, 1.50f, 0.0026f, 0.5f, 0.0010f, 6.0f, 8000.f,  60.f,  250.f, 2.5f, 0.7f, 0.55f, 1, 0.003f, 0.007f, 0.15f, 33.333f},
    {"1965 KOFFER-PLAYER",     1.80f, 1.6f, 2.0f, 0.80f, 0.0060f, 0.9f, 0.0025f, 7.0f, 6000.f, 260.f, 1200.f, 5.0f, 1.0f, 0.30f, 1, 0.004f, 0.004f, 0.20f, 33.333f},
    {"1974 RIEMEN WALNUSS",    3.20f, 2.6f, 3.0f, 1.45f, 0.0028f, 0.5f, 0.0012f, 6.2f, 9500.f,  25.f,    0.f, 0.0f, 0.7f, 0.08f, 0, 0.000f, 0.006f, 0.12f, 33.333f},
    {"1978 DIRECT DRIVE",      1.00f, 1.0f, 1.0f, 1.00f, 0.00045f,0.55f,0.0002f, 7.5f,    0.f,   0.f,    0.f, 0.0f, 0.7f, 0.00f, 0, 0.000f, 0.000f, 0.00f, 33.333f},
    {"1986 BATTLE SCHWARZ",    0.22f, 0.28f,0.45f,0.72f, 0.0002f, 0.55f,0.0001f, 9.0f,    0.f,   0.f,    0.f, 0.0f, 0.7f, 0.05f, 0, 0.000f, 0.000f, 0.00f, 33.333f},
    {"1996 SCRATCH PRO",       0.15f, 0.20f,0.35f,0.62f, 0.0001f, 0.55f,0.0f,    9.0f,    0.f,  30.f, 2600.f, 3.0f, 0.8f, 0.10f, 0, 0.000f, 0.000f, 0.00f, 33.333f},
    {"2006 DVS TIMECODE",      0.10f, 0.15f,0.25f,0.55f, 0.0f,    0.5f, 0.0f,    9.0f,    0.f,   0.f,    0.f, 0.0f, 0.7f, 0.00f, 0, 0.000f, 0.000f, 0.00f, 33.333f},
    {"2026 NEON FUTURE",       0.05f, 0.10f,0.20f,0.50f, 0.0f,    0.5f, 0.0f,    9.0f,    0.f,  20.f,   90.f, 2.0f, 0.7f, 0.12f, 0, 0.000f, 0.000f, 0.00f, 33.333f},
};

// rough loudness match so switching eras does not jump in volume
// 2.4: every era is brought to the loudness of the dry record by the auto gain in readDeck(); the table stays at 1
const float kStyleGain[kNumStyles] = {1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f};

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
        // ---- 2.1 ----
        // the ACTIVE deck: one set of controls on the screen, the plugin mirrors them to deck A or B
        kCPlay, kCSpeed, kCPitch, kCPRange, kCStart, kCBrake, kCOn, kCRev, kCLoop, kCSlot, kCStyle, kCVol,
        kCAngle, kCStrobe, kCCutLed, kCName,
        kSlip, kAutoRun, kLayout, kLayoutTap, kPadCut, kPadHold, kPadCue, kCueTap,
        kDRows, kFRows = kDRows + 7, kFolderPick = kFRows + 7, kFilePick, kFolderStep, kFileStep, kAutoPreview,
        kHLane, kHPhase, kHHit, kSetCueTap, kDSelRow, kFSelRow,
        // ---- 2.2 ----
        kLookTap, kLayoutHint, kCutLatch, kHoldLatch, kFolderOpenTap, kFolderBackTap, kFileLoadTap, kFolderPos, kFilePos,
        kBrPath, kHint, kSync, kDesignName, kPadCutA, kPadCutB, kAFix,
        // ---- 2.3: browser rows by touch: tap = select, swipe = scroll ----
        kDTap = kAFix + 4, kFTap = kDTap + 7, kFolderScroll = kFTap + 7, kFileScroll,
        // ---- 2.4: swipe speed, smooth design change, live resample / live scratch ----
        kSwipeSpeed, kShownC, kShownA, kShownB, kDipC, kDipA, kDipB,
        kLabC, kLabA = kLabC + 10, kLabB = kLabA + 10,
        kFeedSrc = kLabB + 10, kRecTap, kGrabTap, kLiveOn, kLiveSnap, kRecLed, kLiveLed, kFeedInfo, kRecInfo, kFeedMeter,
        // ---- 2.4.1 ----
        kSubFolders,
        // ---- 2.5: MIDI monitor / controller test / platter follow ----
        kMidiMon, kMidiNext, kMidiPrev, kMidiStep, kMidiT1, kMidiT2, kMidiT3, kMidiL1, kMidiStat = kMidiL1 + 8, kMidiFile,
        kPlatFollow, kPlatInfo, kPlatRpm, kPlatSpeed,
        // ---- 2.6: fixed Denon SC6000M profile (from the user's MIDI log) ----
        kCtrlProfile, kPlatDir,
        // ---- 2.7: platter as hand (the SC6000M motor does not turn in computer mode) ----
        kPlatMode,
        // ---- 2.7.1: search for the SC6000M motor command (writes into the MPC's own MIDI connection) ----
        kMotorScan,
        kNumParams
    };

    struct RecJob { std::vector<float> data; int deck = 0, slot = 0; double sr = 44100.0; };
    struct DeckParams { int play, speed, pitch, prange, start, brake, chan, reverse, loop, angle, cutled, strobe, slot, style, vol, name, names; };

    static mpc::PluginInfo makeInfo()
    {
        mpc::PluginInfo i;
        i.name = "SKRATCHA";
        i.vendor = "JJ DA PLUG";
        i.uniqueId = MPC_FOURCC('J', 'J', 's', 'K');   // == "uid" in plugin.json
        i.version = 2720;
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
        std::vector<std::string> styleNames; for (const Style& st : kStyles) styleNames.push_back(st.name);

        addParam(floatParam("level", "Level", -40.0f, 6.0f, -3.0f, "dB", 1));            // param 0: harmless (host nudges it)
        addParam(fixed(intParam("sample", "Sample (1.0)", 1, 64, 1)));                   // 1.0 only, unused
        addParam(boolParam("play", "A Start/Stop", false));
        addParam(choiceParam("speed", "A Speed", {"33", "45"}, 0));
        addParam(floatParam("pitch", "A Pitch", -100.0f, 100.0f, 0.0f, "%", 1));
        addParam(choiceParam("prange", "A Pitch Rng", {"8%", "16%", "50%"}, 0));
        addParam(logParam("start", "A Start Time", 30.0f, 3000.0f, 300.0f, "ms", 0));
        addParam(logParam("brake", "A Brake Time", 30.0f, 5000.0f, 400.0f, "ms", 0));
        addParam(floatParam("srange", "Strip Range", 45.0f, 720.0f, 180.0f, "deg", 0));  // record turn for the whole strip
        addParam(choiceParam("sdir", "Strip Dir", {"NORMAL", "INVERT"}, 0));
        addParam(choiceParam("release", "Release", {"CENTER", "TIMEOUT", "AUTO"}, 2));   // AUTO: centre or the finger stops
        addParam(logParam("smooth", "Smooth", 0.5f, 20.0f, 1.6f, "ms", 1));
        addParam(logParam("catch", "Catch", 5.0f, 500.0f, 15.0f, "ms", 0));
        addParam(choiceParam("curve", "Cut Speed", {"SHARP", "MEDIUM", "SOFT"}, 0));     // CUT pad ramp 0.7 / 3 / 12 ms
        addParam(boolParam("fader", "A On", true));                                       // deck A channel on
        addParam(boolParam("reverse", "A Reverse", false));
        addParam(floatParam("crackle", "Crackle", 0.0f, 100.0f, 0.0f, "%", 0));
        addParam(choiceParam("padbase", "Pad Base", {"C1 36", "C#1 37"}, 0));
        addParam(boolParam("loop", "A Loop", true));
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
        addParam(choiceParam("astyle", "A Style", styleNames, 5));
        addParam(choiceParam("bstyle", "B Style", styleNames, 6));
        addParam(floatParam("avol", "A Volume", -40.0f, 6.0f, 0.0f, "dB", 1));
        addParam(floatParam("bvol", "B Volume", -40.0f, 6.0f, 0.0f, "dB", 1));
        addParam(boolParam("bplay", "B Start/Stop", false));
        addParam(choiceParam("bspeed", "B Speed", {"33", "45"}, 0));
        addParam(floatParam("bpitch", "B Pitch", -100.0f, 100.0f, 0.0f, "%", 1));
        addParam(choiceParam("bprange", "B Pitch Rng", {"8%", "16%", "50%"}, 0));
        addParam(logParam("bstart", "B Start Time", 30.0f, 3000.0f, 300.0f, "ms", 0));
        addParam(logParam("bbrake", "B Brake Time", 30.0f, 5000.0f, 400.0f, "ms", 0));
        addParam(boolParam("bfader", "B On", true));
        addParam(boolParam("breverse", "B Reverse", false));
        addParam(boolParam("bloop", "B Loop", true));
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
        addParam(fixed(intParam("brfolder", "Folder", 1, kMaxEntries, 1)));
        addParam(fixed(intParam("brfile", "File", 1, kMaxEntries, 1)));
        for (int r = 0; r < 5; ++r) { const std::string id = "brrow" + std::to_string(r); text(id.c_str(), ("Row " + std::to_string(r + 1)).c_str()); }
        text("brinfo", "Browser Info");
        addParam(fixed(boolParam("brpreview", "Preview", false)));
        addParam(fixed(choiceParam("brload", "Load To Slot", {"-", "1", "2", "3", "4", "5", "6", "7", "8"}, 0)));
        text("brfname", "Folder Name");
        std::vector<std::string> lessonNames = {"0 GRUNDLAGEN"}; for (const Lesson& l : kLessons) lessonNames.push_back(l.name);
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
        // ---- 2.1: the active deck (same ranges as the deck parameters) ----
        addParam(boolParam("cplay", "Start/Stop", false));
        addParam(choiceParam("cspeed", "Speed", {"33", "45"}, 0));
        addParam(floatParam("cpitch", "Pitch", -100.0f, 100.0f, 0.0f, "%", 1));
        addParam(choiceParam("cprange", "Pitch Range", {"8%", "16%", "50%"}, 0));
        addParam(logParam("cstart", "Start Time", 30.0f, 3000.0f, 300.0f, "ms", 0));
        addParam(logParam("cbrake", "Brake Time", 30.0f, 5000.0f, 400.0f, "ms", 0));
        addParam(boolParam("con", "Deck On", true));
        addParam(boolParam("crev", "Reverse", false));
        addParam(boolParam("cloop", "Loop", true));
        addParam(choiceParam("cslot", "Slot", slotNames, 0));
        addParam(choiceParam("cstyle", "Style", styleNames, 5));
        addParam(floatParam("cvol", "Deck Volume", -40.0f, 6.0f, 0.0f, "dB", 1));
        addParam(live(floatParam("cangle", "Angle", 0.0f, 1.0f, 0.0f, "", 3)));
        addParam(live(floatParam("cstrobe", "Strobe", 0.0f, 1.0f, 0.0f, "", 3)));
        addParam(live(boolParam("ccutled", "Cut LED", true)));
        text("cname", "Record");
        addParam(boolParam("slip", "Slip", false));
        addParam(choiceParam("autorun", "After Scratch", {"STOP", "RUN ON"}, 1));
        addParam(fixed(choiceParam("layout", "Layout", {"STUDIO", "BATTLE", "PADS"}, 0)));
        addParam(fixed(boolParam("laytap", "Layout Tap", false)));
        addParam(live(boolParam("padcut", "Pad Cut", false)));
        addParam(live(boolParam("padhold", "Pad Hold", false)));
        addParam(live(boolParam("padcue", "Pad Cue", false)));
        addParam(fixed(boolParam("cuetap", "Cue Tap", false)));
        for (int r = 0; r < 7; ++r) { const std::string id = "drow" + std::to_string(r); text(id.c_str(), ("Folder Row " + std::to_string(r + 1)).c_str()); }
        for (int r = 0; r < 7; ++r) { const std::string id = "frow" + std::to_string(r); text(id.c_str(), ("File Row " + std::to_string(r + 1)).c_str()); }
        addParam(fixed(choiceParam("dpick", "Folder Pick", {"-", "1", "2", "3", "4", "5", "6", "7"}, 0)));
        addParam(fixed(choiceParam("fpick", "File Pick", {"-", "1", "2", "3", "4", "5", "6", "7"}, 0)));
        addParam(fixed(choiceParam("dstep", "Folder Step", {"-", "UP", "DOWN", "PAGE UP", "PAGE DOWN"}, 0)));
        addParam(fixed(choiceParam("fstep", "File Step", {"-", "UP", "DOWN", "PAGE UP", "PAGE DOWN"}, 0)));
        addParam(fixed(boolParam("autoprev", "Auto Preview", true)));
        addParam(live(intParam("hlane", "Lane", 0, 31, 0)));
        text("hphase", "Phase");
        addParam(live(intParam("hhit", "Step Hit", 0, 2, 0)));
        addParam(fixed(boolParam("setcue", "Set Cue Tap", false)));
        addParam(live(intParam("dsel", "Folder Sel Row", 0, 7, 0)));
        addParam(live(intParam("fsel", "File Sel Row", 0, 7, 0)));
        // ---- 2.2 ----
        addParam(fixed(boolParam("looktap", "Look Tap", false)));             // hidden round button: next turntable era
        text("layhint", "Layout Hint");
        addParam(boolParam("cutlatch", "Cut Latch", false));                   // CUT by touch (tap on, tap off)
        addParam(boolParam("holdlatch", "Hold Latch", false));                 // HOLD by touch
        addParam(fixed(boolParam("dopen", "Folder Open", false)));
        addParam(fixed(boolParam("dback", "Folder Back", false)));
        addParam(fixed(boolParam("fload", "File Load", false)));
        addParam(fixed(floatParam("dpos", "Folder Pos", 0.0f, 1.0f, 1.0f, "", 3)));
        addParam(fixed(floatParam("fpos", "File Pos", 0.0f, 1.0f, 1.0f, "", 3)));
        text("brpath", "Path");
        addParam(live(intParam("hint", "Hint", 0, 16, 0)));
        addParam(live(intParam("sync", "Sync", 0, 10, 0)));
        text("design", "Design");
        addParam(live(boolParam("padcuta", "Pad Cut A", false)));
        addParam(live(boolParam("padcutb", "Pad Cut B", false)));
        for (int k = 0; k < 4; ++k) { const std::string id = "afix" + std::to_string(k + 1); text(id.c_str(), ("Deck A Slot " + std::to_string(k + 1)).c_str()); }
        // ---- 2.3 ----
        for (int r = 0; r < 7; ++r) addParam(fixed(boolParam(("dtap" + std::to_string(r + 1)).c_str(), ("Folder Tap " + std::to_string(r + 1)).c_str(), false)));
        for (int r = 0; r < 7; ++r) addParam(fixed(boolParam(("ftap" + std::to_string(r + 1)).c_str(), ("File Tap " + std::to_string(r + 1)).c_str(), false)));
        addParam(fixed(floatParam("dscroll", "Folder Scroll", 0.0f, 1.0f, 0.5f, "", 3)));
        addParam(fixed(floatParam("fscroll", "File Scroll", 0.0f, 1.0f, 0.5f, "", 3)));
        // ---- 2.4 ----
        addParam(choiceParam("swipe", "Swipe Speed", {"LANGSAM", "NORMAL", "SCHNELL"}, 1));
        addParam(fixed(intParam("shownc", "Shown Style", 0, kNumStyles - 1, 5)));
        addParam(fixed(intParam("showna", "Shown A Style", 0, kNumStyles - 1, 5)));
        addParam(fixed(intParam("shownb", "Shown B Style", 0, kNumStyles - 1, 5)));
        addParam(fixed(floatParam("dipc", "Dip", 0.0f, 1.0f, 0.0f, "", 2)));
        addParam(fixed(floatParam("dipa", "A Dip", 0.0f, 1.0f, 0.0f, "", 2)));
        addParam(fixed(floatParam("dipb", "B Dip", 0.0f, 1.0f, 0.0f, "", 2)));
        for (const char* k : {"c", "a", "b"})
            for (int i = 0; i < kNumStyles; ++i)
            {
                const std::string id = std::string("lab") + k + std::to_string(i);
                const std::string nm = std::string(k[0] == 'c' ? "" : (k[0] == 'a' ? "A " : "B ")) + "Label " + std::to_string(i);
                addParam(fixed(floatParam(id.c_str(), nm.c_str(), 0.0f, 1.0f, 0.0f, "", 3)));
            }
        addParam(choiceParam("feedsrc", "Feed Source", {"FEED 1", "FEED 2", "FEED 3", "FEED 4"}, 0));
        addParam(fixed(boolParam("rectap", "Rec Tap", false)));
        addParam(fixed(choiceParam("grab", "Grab", {"-", "2 S", "4 S", "8 S"}, 0)));
        addParam(fixed(boolParam("liveon", "Live", false)));
        addParam(choiceParam("livesnap", "Live Release", {"SOFORT ZURUECK", "BLEIBT HINTEN"}, 0));
        addParam(fixed(boolParam("recled", "Rec LED", false)));
        addParam(fixed(boolParam("liveled", "Live LED", false)));
        text("feedinfo", "Feed Info");
        text("recinfo", "Rec Info");
        addParam(fixed(floatParam("feedmeter", "Feed Meter", 0.0f, 1.0f, 0.0f, "", 2)));
        addParam(boolParam("subdirs", "Sub Folders", true));    // browser: also every sound in the folders below
        // ---- 2.5 ----
        addParam(fixed(boolParam("midimon", "Midi Monitor", false)));
        addParam(fixed(boolParam("midinext", "Midi Next", false)));
        addParam(fixed(boolParam("midiprev", "Midi Prev", false)));
        addParam(fixed(intParam("midistep", "Midi Step", 0, kNumTestSteps - 1, 0)));
        text("midit1", "Test Line 1"); text("midit2", "Test Line 2"); text("midit3", "Test Line 3");
        for (int i = 0; i < 8; ++i) { const std::string id = "midil" + std::to_string(i + 1); text(id.c_str(), ("Midi Line " + std::to_string(i + 1)).c_str()); }
        text("midistat", "Midi Stats"); text("midifile", "Midi File");
        addParam(fixed(boolParam("platfollow", "Platter Follow", false)));
        text("platinfo", "Platter Info");
        addParam(choiceParam("platrpm", "Platter RPM", {"33 1/3", "45"}, 0));
        text("platspeed", "Platter Speed");
        addParam(choiceParam("ctrlprof", "Controller", {"LERNEN", "SC6000M"}, 0));
        addParam(choiceParam("platdir", "Platter Dir", {"NORMAL", "UMGEKEHRT"}, 0));
        // HAND: the platter is your hand on the record, SKRATCHA's own motor plays it (PLAY = start/stop);
        // MOTOR: the platter is the record itself (only when its motor really turns)
        addParam(choiceParam("platmode", "Platter Mode", {"HAND", "MOTOR"}, 0));
        addParam(fixed(boolParam("motorscan", "Motor Scan", false)));
        if (numParams() != kNumParams) mpc::log("SKRATCHA: parameter count mismatch %d %d", numParams(), (int)kNumParams);

        deckP_[0] = {kPlay, kSpeed, kPitch, kPitchRange, kStart, kBrake, kFader, kReverse, kLoop, kAngle, kCutLed, kStrobe, kASlot, kAStyle, kAVol, kAName, kANames};
        deckP_[1] = {kBPlay, kBSpeed, kBPitch, kBPitchRange, kBStart, kBBrake, kBFader, kBReverse, kBLoop, kBAngle, kBCutLed, kBStrobe, kBSlot, kBStyle, kBVol, kBName, kBNames};

        const int mirror[kNumMirrors][3] = {
            {kCPlay, kPlay, kBPlay}, {kCSpeed, kSpeed, kBSpeed}, {kCPitch, kPitch, kBPitch}, {kCPRange, kPitchRange, kBPitchRange},
            {kCStart, kStart, kBStart}, {kCBrake, kBrake, kBBrake}, {kCOn, kFader, kBFader}, {kCRev, kReverse, kBReverse},
            {kCLoop, kLoop, kBLoop}, {kCSlot, kASlot, kBSlot}, {kCStyle, kAStyle, kBStyle}, {kCVol, kAVol, kBVol}};
        for (int i = 0; i < kNumMirrors; ++i) for (int k = 0; k < 3; ++k) mirror_[i][k] = mirror[i][k];

        buildPrograms();

        // built-in records fill the slots until the user loads others (or a project restores its own)
        builtInDir_ = mpc::contentPath("Samples");
        std::vector<std::string> builtIns;
        listWavs(builtInDir_, builtIns);
        for (int s = 0; s < kSlots && !builtIns.empty(); ++s)
        {
            want_[0][s] = builtIns[(size_t)s % builtIns.size()];
            want_[1][s] = builtIns[(size_t)(s + 8) % builtIns.size()];   // deck B starts on the break
        }
        if (const char* t = std::getenv("SKRATCHA_TEST_SLOT8")) want_[0][7] = t;   // test harness only
    }

    ~SKRATCHA() override
    {
        stopThread_.store(true);
        if (worker_.joinable()) worker_.join();
        if (loader_.joinable()) loader_.join();
        if (scanner_.joinable()) scanner_.join();
        if (motor_.joinable()) motor_.join();
        for (int d = 0; d < 2; ++d)
            for (int s = 0; s < kSlots; ++s)
            {
                delete deck_[d].slot[s];
                delete pending_[d][s].exchange(nullptr);
                delete retired_[d][s].exchange(nullptr);
            }
        delete preview_; delete previewPending_.exchange(nullptr); delete previewRetired_.exchange(nullptr);
        if (skrfeed::Shared* f = feed_.exchange(nullptr)) { f->h.liveOn.store(0); skrfeed::unmapChannel(f); }
        for (skrfeed::Shared*& r : feedRetired_) { skrfeed::unmapChannel(r); r = nullptr; }
        delete liveRec_;
        delete recJob_;
        if (logFp_ != nullptr) { std::fflush(logFp_); std::fclose(logFp_); logFp_ = nullptr; }
    }

    // ---------------------------------------------------------------------------------------------------------
    void prepare(double sampleRate, int maxBlockSize) override
    {
        sr_ = sampleRate > 1000.0 ? sampleRate : 44100.0;
        maxBlock_ = mpc::clamp(maxBlockSize, 32, 4096);
        liveLag_ = (double)(maxBlock_ + 96);
        if (liveRec_ == nullptr)
        {
            // the LIVE record: a ring of the FEED audio with its mip levels, filled block by block
            liveRec_ = new Record();
            liveRec_->name = "LIVE"; liveRec_->path = ""; liveRec_->channels = 2; liveRec_->sampleRate = sr_;
            liveRec_->length = kLiveN;
            for (int k = 0; k < kMipLevels; ++k)
            {
                liveRec_->len[k] = kLiveN >> k;
                for (int c = 0; c < 2; ++c) liveRec_->lv[k][c].assign(kLiveN >> k, 0.0f);
            }
        }
        agCoef_ = (float)(1.0 - std::exp(-1.0 / (0.25 * sr_)));
        agHpCoef_ = (float)(1.0 - std::exp(-2.0 * 3.14159265 * 500.0 / sr_));
        agSmooth_ = (float)(1.0 - std::exp(-1.0 / (0.04 * sr_)));
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
            scanner_ = std::thread([this] { scanLoop(); });
            loader_ = std::thread([this] { loaderLoop(); });
            worker_ = std::thread([this] { reporterLoop(); });
            motor_ = std::thread([this] { motorLoop(); });
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
        tourActive_ = false;
        if ((prevDemo_ || prevRun_) && getInt(kHLesson) > 0) { teacher_.demo = prevDemo_; teacher_.start(mpc::clamp(getInt(kHLesson) - 1, 0, kNumLessons - 1)); }
        syncMirrors(true);
        lastLayoutTap_ = getNormalised(kLayoutTap); lastCueTap_ = getNormalised(kCueTap); lastSetCueTap_ = getNormalised(kSetCueTap);
        lastLookTap_ = getNormalised(kLookTap); lastCutLatch_ = getNormalised(kCutLatch); lastHoldLatch_ = getNormalised(kHoldLatch);
    }

    // ---------------------------------------------------------------------------------------------------------
    void process(mpc::ProcessContext& ctx) override
    {
        swapIn();
        syncMirrors(false);
        liveBlock(ctx.numFrames);
        midiMonOn_ = getBool(kMidiMon);
        if (getInt(kCtrlProfile) == 1)
        {
            const float tpc = (getInt(kPlatDir) == 1 ? 1.0f : -1.0f) / 3600.0f;
            if (platDec_.kind.load(std::memory_order_relaxed) != skr::PlatterDecoder::kVel14 || platDec_.turnsPerCount.load(std::memory_order_relaxed) != tpc)
            {
                platDec_.status.store(0xB0); platDec_.d1.store(54); platDec_.baseCh.store(0);
                platDec_.turnsPerCount.store(tpc);
                platDec_.kind.store(skr::PlatterDecoder::kVel14);
            }
        }
        {
            const bool f = (getBool(kPlatFollow) || getInt(kCtrlProfile) == 1) && platDec_.kind.load() != skr::PlatterDecoder::kNone;   // SC6000M: the platter always drives
            if (!f && platFollowOn_) for (Deck& X : deck_) if (X.handActive && handSrc_ == kSrcJog) letGo(X);
            if (f && !platFollowOn_) { platLast_[0] = platLast_[1] = -1; }
            platFollowOn_ = f;
        }
        // hidden layout button (the round target light) and the screen CUE / SET CUE keys: every tap flips them
        if (getNormalised(kLayoutTap) != lastLayoutTap_)
        {
            lastLayoutTap_ = getNormalised(kLayoutTap);
            setFromAudio(kLayout, (float)((getInt(kLayout) + 1) % 3));
        }
        if (getNormalised(kCueTap) != lastCueTap_) { lastCueTap_ = getNormalised(kCueTap); Deck& D = deck_[activeDeck_]; jumpTo(D, D.cue[D.cur]); cueFlash_ = (int)(0.15 * sr_); }
        if (getNormalised(kSetCueTap) != lastSetCueTap_) { lastSetCueTap_ = getNormalised(kSetCueTap); Deck& D = deck_[activeDeck_]; D.cue[D.cur] = D.x; cueFlash_ = (int)(0.3 * sr_); }
        // hidden round button: the active deck becomes the next turntable era (look, feel and sound)
        if (getNormalised(kLookTap) != lastLookTap_)
        {
            lastLookTap_ = getNormalised(kLookTap);
            const int sp = deckP_[activeDeck_].style;
            setFromAudio(sp, (float)((getInt(sp) + 1) % kNumStyles));
        }
        // CUT and HOLD by touch: tap on, tap off
        if (getNormalised(kCutLatch) != lastCutLatch_) { lastCutLatch_ = getNormalised(kCutLatch); cutLatchDeck_ = activeDeck_; }
        if (getNormalised(kHoldLatch) != lastHoldLatch_)
        {
            lastHoldLatch_ = getNormalised(kHoldLatch);
            Deck& D = deck_[activeDeck_];
            if (getBool(kHoldLatch)) { padHold_ = true; grab(kSrcPad); anchorSrc_ = kSrcPad; D.rawTarget = D.handTarget = D.x; D.interpLeft = 0; }
            else { padHold_ = false; if (D.handActive && handSrc_ == kSrcPad) letGo(D); }
        }
        readBlockParams(ctx.numFrames);
        eventClock_ = blockClock_;
        pollParamHands(ctx.numFrames);

        int pos = 0;
        for (int e = 0; e < ctx.numMidiEvents; ++e)
        {
            const mpc::MidiEvent& ev = ctx.midi[e];
            if (ev.sampleOffset > pos) { render(ctx, pos, ev.sampleOffset); pos = ev.sampleOffset; }
            eventClock_ = blockClock_ + ev.sampleOffset;
            if ((ev.data[0] & 0xF0) == 0xB0 && (ev.data[1] == 54 || ev.data[1] == 55)) platFrames_.fetch_add(1, std::memory_order_relaxed);
            { skr::MidiRec r; r.clock = (uint64_t)eventClock_; r.n = ev.size; r.b[0] = ev.data[0]; r.b[1] = ev.data[1]; r.b[2] = ev.data[2]; midiRing_.push(r); }
            if (scEvent(ev)) continue;
            if (platterEvent(ev)) continue;
            if (platFollowOn_ && ctrlKnown(ev)) continue;        // other controller messages (heartbeat, keys) do not trigger pads
            if (midiMonOn_ && !platFollowOn_) continue;          // while the test runs, the controller does not play the decks
            handleMidi(ev);
        }
        render(ctx, pos, ctx.numFrames);
        blockClock_ += ctx.numFrames;
        if (skrfeed::Shared* f = liveFeed_)
        {
            if (retOn_) f->h.retPos.store(liveHeadU_ + (uint64_t)ctx.numFrames, std::memory_order_release);
            if (liveDeck_ >= 0) { f->h.liveOn.store(1, std::memory_order_relaxed); f->h.skrAlive.fetch_add(1, std::memory_order_relaxed); }
        }
        liveLedOn_.store(liveDeck_ >= 0);

        // live values for the background reporter
        for (int d = 0; d < 2; ++d)
        {
            Deck& D = deck_[d];
            if (!std::isfinite(D.x)) { D.x = 0.0; D.handTarget = D.rawTarget = 0.0; D.interpLeft = 0; D.handVel = D.vel = 0.0; }
            const Record* r = recOf(D);
            liveRevs_[d].store((r != nullptr ? D.x / r->sampleRate : D.x / sr_) * kRevPerSecond33 * kStyles[D.style].rpm / 33.333);
            liveCut_[d].store(D.audible * D.cutGain > 0.3f);
            liveSlot_[d].store(D.cur);
        }
        Deck& A = deck_[activeDeck_];
        liveStrip_.store(A.handActive ? stripLedFrame_ : 0);
        liveActive_.store(activeDeck_);
        liveGhost_.store(teacher_.running ? 1 + mpc::clamp((int)std::lround((teacher_.ghost * 0.5f + 0.5f) * (kStripFrames - 2)), 0, kStripFrames - 2) : 0);
        liveBeat_.store(teacher_.running ? teacher_.beat : 0);
        liveFadeLed_.store(teacher_.running && teacher_.faderTarget);
        liveMsg_.store(getInt(kHLesson) == 0 ? tourMsg_ : teacher_.msg);
        liveScore_.store(teacher_.scorePct + 1000 * teacher_.bar);
        if (teacher_.starsNew) { teacher_.starsNew = false; liveStars_.store(teacher_.stars); for (int l = 0; l < kNumLessons; ++l) liveBest_[l].store(teacher_.best[l]); }
        if (previewDoneFlag_) { previewDoneFlag_ = false; previewDone_.store(true); }
        livePadCut_.store(cutHeld_ || cutLatchOn_);
        livePadCutA_.store((cutHeld_ && cutDeck_ == 0) || (cutLatchOn_ && cutLatchDeck_ == 0));
        livePadCutB_.store((cutHeld_ && cutDeck_ == 1) || (cutLatchOn_ && cutLatchDeck_ == 1));
        livePadHold_.store(padHold_);
        liveSync_.store(teacher_.running ? teacher_.sync : 0);
        if (cueFlash_ > 0) cueFlash_ -= ctx.numFrames;
        livePadCue_.store(cueFlash_ > 0 || cueHeld_);
        liveLane_.store(teacher_.lane);
        livePhase_.store(teacher_.phase * 10 + teacher_.countBeat);
        liveHit_.store(teacher_.hit);
    }

    // one set of controls on the screen for the active deck: copy changes both ways
    void syncMirrors(bool force)
    {
        const int d = activeDeck_;
        for (int i = 0; i < kNumMirrors; ++i)
        {
            const int px = mirror_[i][0], dp = mirror_[i][1 + d];
            const float pv = getNormalised(px), dv = getNormalised(dp);
            if (force)
            {
                if (pv != dv) { setNormalised(px, dv); markDirty(px); }
                mirrorP_[i] = dv; mirrorD_[i] = dv;
            }
            else if (pv != mirrorP_[i]) { setNormalised(dp, pv); markDirty(dp); mirrorP_[i] = pv; mirrorD_[i] = pv; readLater_ = true; }
            else if (dv != mirrorD_[i]) { setNormalised(px, dv); markDirty(px); mirrorP_[i] = dv; mirrorD_[i] = dv; }
        }
    }

    void markDirty(int index) { dirty_[index >> 6].fetch_or(1ull << (index & 63)); }

    void parameterChanged(int index, float plainValue) override
    {
        if (index == kRescan && plainValue >= 0.5f) rescanRequested_.store(true);
        else if (index == kBrLoad && plainValue >= 0.5f) loadRequest_.store((int)std::lround(plainValue));
    }

    bool formatValue(int index, float plainValue, std::string& out) override
    {
        static const float ranges[3] = {8.0f, 16.0f, 50.0f};
        if (index == kPitch || index == kBPitch || index == kCPitch)
        {
            const int rp = index == kPitch ? kPitchRange : index == kBPitch ? kBPitchRange : kCPRange;
            const float pct = plainValue * 0.01f * ranges[mpc::clamp(getInt(rp), 0, 2)];
            out = fmt("%+.2f%%", pct); return true;
        }
        if (index == kStripRange) { out = fmt("%.0f deg", plainValue); return true; }
        if (index == kPlay || index == kBPlay || index == kCPlay) { out = plainValue >= 0.5f ? "PLAY" : "STOP"; return true; }
        if (index == kFader || index == kBFader || index == kCOn) { out = plainValue >= 0.5f ? "ON" : "OFF"; return true; }
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
        if (index == kFeedInfo) { out = feedInfo_; return true; }
        if (index >= kMidiT1 && index <= kMidiT3) { out = midiTxt_[index - kMidiT1]; return true; }
        if (index >= kMidiL1 && index < kMidiL1 + 8) { out = midiLines_[index - kMidiL1]; return true; }
        if (index == kMidiStat) { out = midiStat_; return true; }
        if (index == kMidiFile) { out = midiFile_; return true; }
        if (index == kPlatInfo) { out = platInfo_; return true; }
        if (index == kPlatSpeed) { out = platSpeed_; return true; }
        if (index == kRecInfo) { out = recInfo_; return true; }
        if (index == kAName || index == kBName)
        {
            const int d = index == kAName ? 0 : 1;
            const int s = liveSlot_[d].load();
            out = std::string(d ? "B" : "A") + " " + std::to_string(s + 1) + "  " + slotName_[d][s];
            return true;
        }
        if (index == kCName)
        {
            const int d = liveActive_.load(), s = liveSlot_[d].load();
            out = std::string(d ? "B" : "A") + " " + std::to_string(s + 1) + "  " + slotName_[d][s];
            return true;
        }
        if (index >= kANames && index < kANames + kSlots)       // the 8 slots of the ACTIVE deck
        {
            out = slotName_[liveActive_.load()][index - kANames];
            return true;
        }
        if (index >= kBNames && index < kBNames + kSlots) { out = slotName_[1][index - kBNames]; return true; }
        if (index >= kAFix && index < kAFix + 4) { out = slotName_[0][index - kAFix]; return true; }
        if (index >= kDRows && index < kDRows + 7)
        {
            const int f = folderTop_.load() + index - kDRows;
            out = "";
            if (listing_.load() && index == kDRows) { out = "LESE ORDNER ..."; return true; }
            if (f >= 0 && f < (int)dirs_.size())
            {
                const DirEntry& e = dirs_[(size_t)f];
                std::string t = e.kind == 0 ? std::string("[..] ZURUECK") : e.name;
                if (e.kind == 1) { for (char& ch : t) ch = (char)std::toupper((unsigned char)ch); t = "[ ] " + t; }
                if (t.size() > 27) t = t.substr(0, 27);
                out = (f == getInt(kBrFolder) - 1 ? "> " : "") + t;
            }
            return true;
        }
        if (index >= kFRows && index < kFRows + 7)
        {
            const int i = fileTop_.load() + index - kFRows;
            out = "";
            if (i >= 0 && i < (int)files_.size()) out = (i == getInt(kBrFile) - 1 ? "> " : "") + displayName(fileOf(files_[(size_t)i]), 27);
            else if (i == 0 && files_.empty() && !listing_.load()) out = "(KEINE SOUNDS HIER)";
            return true;
        }
        if (index == kBrPath)
        {
            out = cwd_.empty() ? std::string("ALLE LAUFWERKE") : cwd_;
            if (out.size() > 31) out = "..." + out.substr(out.size() - 28);
            return true;
        }
        if (index == kDesignName)
        {
            const int d = liveActive_.load();
            out = kStyles[mpc::clamp(getInt(deckP_[d].style), 0, kNumStyles - 1)].name;
            return true;
        }
        if (index == kLayoutHint)
        {
            static const char* const now[3] = {"STUDIO", "BATTLE", "PADS"};
            static const char* const next[3] = {"BATTLE", "PADS", "STUDIO"};
            const int l = mpc::clamp(getInt(kLayout), 0, 2);
            out = std::string("JETZT ") + now[l] + "  >  " + next[l];
            return true;
        }
        if (index == kHPhase && getInt(kHLesson) == 0)
        {
            out = liveTour_.load() >= kTourSteps ? "GESCHAFFT!" : (getBool(kHRun) ? "GRUNDLAGEN - MACH MIT" : "GRUNDLAGEN");
            return true;
        }
        if (index == kHPhase)
        {
            const int ph = livePhase_.load();
            switch (ph / 10)
            {
                case 1: out = "HOER ZU - SO KLINGT ES"; break;
                case 2: out = "ZAEHL MIT ...  " + std::to_string(ph % 10); break;
                case 3: out = "JETZT DU!"; break;
                default: out = "BEREIT"; break;
            }
            return true;
        }
        if (index == kBrFolder || index == kBrFolderName)
        {
            const int f = getInt(kBrFolder) - 1;
            out = (f >= 0 && f < (int)dirs_.size()) ? (dirs_[(size_t)f].kind == 0 ? std::string("[..] ZURUECK") : dirs_[(size_t)f].name) : std::string("-");
            if (out.size() > 31) out = out.substr(0, 31);
            return true;
        }
        if (index == kBrFile || (index >= kBrRows && index < kBrRows + 5))
        {
            const int sel = getInt(kBrFile) - 1 + (index == kBrFile ? 0 : index - kBrRows - 2);
            out = (sel >= 0 && sel < (int)files_.size()) ? displayName(fileOf(files_[(size_t)sel]), 29) : std::string("");
            return true;
        }
        if (index == kBrInfo)
        {
            const int files = (int)files_.size();
            out = (filesSearching_ ? std::string("SUCHE ... ") : std::string("SOUND ")) + std::to_string(std::min(getInt(kBrFile), files)) + "/" + std::to_string(files);
            if (filesDeep_ && !filesSearching_) out += " (MIT UNTERORDNERN)";
            return true;
        }
        if (index == kHMsg) { out = kMsgText[mpc::clamp(liveMsg_.load(), 0, kNumMsgs - 1)]; return true; }
        if (index == kHText1 || index == kHText2)
        {
            if (getInt(kHLesson) == 0)
            {
                const TourStep& T = kTour[mpc::clamp(liveTour_.load(), 0, kTourSteps)];
                out = index == kHText1 ? T.line1 : T.line2;
                if (!getBool(kHRun) && liveTour_.load() == 0) out = index == kHText1 ? "GRUNDLAGEN: ALLES IN 10 SCHRITTEN" : "TIPPE UEBEN - ICH ZEIGE DIR ALLES";
                return true;
            }
            const Lesson& L = kLessons[mpc::clamp(getInt(kHLesson) - 1, 0, kNumLessons - 1)];
            out = index == kHText1 ? L.line1 : L.line2; return true;
        }
        if (index == kHScore && getInt(kHLesson) == 0)
        {
            out = "SCHRITT " + std::to_string(std::min(liveTour_.load() + 1, kTourSteps)) + " VON " + std::to_string(kTourSteps);
            return true;
        }
        if (index == kHScore)
        {
            const int l = mpc::clamp(getInt(kHLesson) - 1, 0, kNumLessons - 1);
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
        // era tone
        float hpCoef = 0.0f, hpL = 0.0f, hpR = 0.0f, hiss = 0.0f, drive = 0.0f, driveNorm = 1.0f;
        // loudness match: weighted power of the dry and the era-coloured signal, gain = sqrt(dry / wet)
        float agDry = 0.0f, agWet = 0.0f, agHd = 0.0f, agHw = 0.0f, ag = 1.0f, agTarget = 1.0f; int agCount = 0;
        bool mono = false, peakOn = false;
        int peakStyle = -1;
        float pb0 = 1, pb1 = 0, pb2 = 0, pa1 = 0, pa2 = 0, pz[2][2] = {{0, 0}, {0, 0}};
        // slip shadow: where the record would be without the hand
        double slipX = 0.0, slipVel = 0.0;
        bool slipValid = false;
        // LIVE: the deck plays the FEED ring instead of its slot (savedX = where the slot record was)
        bool live = false, savedMotor = false;
        double savedX = 0.0;
    };

    enum Source { kSrcNone = 0, kSrcPitchBend, kSrcModWheel, kSrcScratch, kSrcJog, kSrcPad, kSrcHelper };

    // ---------------------------------------------------------------------------------------------------------
    void buildPrograms()
    {
        auto base = [this]() { std::vector<float> v((size_t)numParams()); for (int i = 0; i < numParams(); ++i) v[(size_t)i] = param(i).def; return v; };
        auto lesson = [](std::vector<float>& v, int l) { v[kHLesson] = (float)(l + 1); v[kHBpm] = kLessons[l].bpm; v[kCutMode] = kLessons[l].openMode ? 1.0f : 0.0f; };
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

    // ---- LIVE: copy the new FEED frames into the live ring, build its mips, start / stop the live deck ----
    void liveBlock(int frames)
    {
        (void)frames;
        skrfeed::Shared* f = feed_.load(std::memory_order_acquire);
        if (f != liveFeed_ && liveFeed_ != nullptr && liveDeck_ >= 0) liveFeed_->h.liveOn.store(0);
        liveFeed_ = f;
        retOn_ = false;
        bool feedOk = false;
        if (f != nullptr && liveRec_ != nullptr)
        {
            const uint64_t w = f->h.writePos.load(std::memory_order_acquire);
            const uint32_t alive = f->h.feedAlive.load(std::memory_order_relaxed);
            if (alive != lastFeedAlive_) { lastFeedAlive_ = alive; feedIdle_ = 0; } else if (feedIdle_ < 100000000) feedIdle_ += frames;
            feedOk = feedIdle_ < (int)(0.5 * sr_);
            if (liveIn_ > w || w - liveIn_ > (uint64_t)(kLiveN / 2))
            {
                liveIn_ = w > 8192 ? w - 8192 : 0;          // (re)connect: start a fresh history
                for (int k = 0; k < kMipLevels; ++k) liveCnt_[k] = liveIn_ >> k;
            }
            const uint32_t fsr = f->h.sampleRate.load(std::memory_order_relaxed);
            if (fsr > 1000) liveRec_->sampleRate = (double)fsr;
            std::vector<float>& L0 = liveRec_->lv[0][0];
            std::vector<float>& R0 = liveRec_->lv[0][1];
            while (liveIn_ < w)
            {
                const uint32_t ci = (uint32_t)(liveIn_ & skrfeed::kCapMask), li = (uint32_t)(liveIn_ & (kLiveN - 1));
                L0[li] = f->cap[2 * ci]; R0[li] = f->cap[2 * ci + 1];
                ++liveIn_;
            }
            liveCnt_[0] = liveIn_;
            for (int k = 1; k < kMipLevels; ++k)
            {
                const uint32_t srcMask = (kLiveN >> (k - 1)) - 1, dstMask = (kLiveN >> k) - 1;
                const int half = (HalfbandFir::N - 1) / 2;
                while (2 * liveCnt_[k] + (uint64_t)half < liveCnt_[k - 1])
                {
                    const int64_t centre = (int64_t)(2 * liveCnt_[k]);
                    for (int c = 0; c < 2; ++c)
                    {
                        const std::vector<float>& src = liveRec_->lv[k - 1][c];
                        float acc = 0.0f;
                        for (int t = 0; t < HalfbandFir::N; ++t)
                        {
                            const int64_t idx = centre + t - half;
                            if (idx >= 0) acc += fir_.h[t] * src[(size_t)((uint64_t)idx & srcMask)];
                        }
                        liveRec_->lv[k][c][(size_t)(liveCnt_[k] & dstMask)] = std::fabs(acc) < 1e-20f ? 0.0f : acc;
                    }
                    ++liveCnt_[k];
                }
            }
            liveHeadU_ = w;
            liveHead_ = (double)w;
        }
        const bool want = getBool(kLiveOn) && feedOk;
        if (want && liveDeck_ < 0) startLive(activeDeck_);
        else if (!want && liveDeck_ >= 0) stopLive();
        if (getBool(kLiveOn) && f == nullptr && feedLostBlocks_++ > (int)(1.0 * sr_ / std::max(1, frames))) { setFromAudio(kLiveOn, 0.0f); feedLostBlocks_ = 0; }
        if (f != nullptr) feedLostBlocks_ = 0;
        retOn_ = liveDeck_ >= 0 && f != nullptr && f->h.replaceMode.load(std::memory_order_relaxed) == 1;
    }

    void startLive(int d)
    {
        Deck& D = deck_[d];
        D.savedX = D.x;
        D.savedMotor = D.motorOn;
        if (const Record* old = D.slot[D.cur]) { D.xOldRec = old; D.xOld = D.x; D.xfade = 1.0f; }
        D.live = true;
        liveDeck_ = d;
        placeAt(D, liveHead_ - liveLag_);                // "now" in the track
        if (!D.motorOn) { setFromAudio(deckP_[d].play, 1.0f); refreshMotors(); }
        D.vel = liveRec_->sampleRate / sr_; D.catching = false;
    }

    void stopLive()
    {
        Deck& D = deck_[liveDeck_];
        if (D.handActive) letGo(D);
        D.xOldRec = liveRec_; D.xOld = D.x; D.xfade = 1.0f;
        D.live = false;
        placeAt(D, D.savedX);
        if (!D.savedMotor && D.motorOn) { setFromAudio(deckP_[liveDeck_].play, 0.0f); refreshMotors(); D.vel = 0.0; }
        if (liveFeed_ != nullptr) liveFeed_->h.liveOn.store(0);
        liveDeck_ = -1;
    }

    // the live deck never reads ahead of the FEED (no data yet) nor further back than the ring holds
    void clampLive(Deck& D)
    {
        const double hi = liveHead_ - 64.0, lo = liveHead_ - (double)kLiveN + 16384.0;
        if (D.x > hi) { D.x = hi; if (D.vel > 0.0 && !D.handActive) D.vel = std::min(D.vel, liveRec_->sampleRate / sr_); }
        else if (D.x < lo) D.x = lo;
    }

    const Record* recOf(const Deck& D) const { return (D.live && liveRec_ != nullptr) ? liveRec_ : D.slot[D.cur]; }

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
            syncMirrors(true);
        }

        const double tauBase = get(kSmooth) * 0.001 * sr_;
        const double catchBase = get(kCatch) * 0.001 * sr_;
        const float xf = get(kXFader) * 0.01f, xc = get(kXCurve) * 0.01f, lag = get(kXLag) * 0.01f;
        const bool ham = getBool(kHamster);
        static const float cutMs[3] = {0.7f, 3.0f, 12.0f};
        cutStep_ = 1.0f / std::max(1.0f, cutMs[mpc::clamp(getInt(kCurve), 0, 2)] * 0.001f * (float)sr_);
        cutOpenMode_ = getInt(kCutMode) == 1;
        layout_ = getInt(kLayout);
        slipOn_ = getBool(kSlip);
        cutLatchOn_ = getBool(kCutLatch);
        autoRun_ = getInt(kAutoRun) == 1;
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
            const Record* r = recOf(D);
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
            D.samplesPerRev = fileSr / (kRevPerSecond33 * St.rpm / 33.333);
            D.stripScale = (get(kStripRange) / 360.0) * D.samplesPerRev * 0.5 * (getInt(kStripDir) == 1 ? -1.0 : 1.0);
            D.loop = true;                       // the record always loops (a locked groove): there is always sound

            // wow & flutter: evaluated at block edges, linear in between (no per-sample sin)
            const double secs = frames / sr_;
            const double w0 = D.wowNow;
            D.wowPh += St.wowHz * secs; D.wowPh -= std::floor(D.wowPh);
            D.flutPh += St.flutterHz * secs; D.flutPh -= std::floor(D.flutPh);
            const double w1 = St.wow * std::sin(2.0 * kPi * D.wowPh) + St.flutter * std::sin(2.0 * kPi * D.flutPh);
            D.wowNow = w0; D.wowStep = (w1 - w0) / std::max(1, frames);
            D.lpCoef = St.lpHz > 0.0f ? (float)(1.0 - std::exp(-2.0 * kPi * St.lpHz / sr_)) : 1.0f;
            D.hpCoef = St.hpHz > 0.0f ? (float)(1.0 - std::exp(-2.0 * kPi * St.hpHz / sr_)) : 0.0f;
            D.mono = St.mono != 0; D.hiss = St.hiss;
            D.drive = St.drive; D.driveNorm = St.drive > 0.0f ? 1.0f / softClip(1.0f + St.drive * 4.0f) : 1.0f;
            if (St.peakDb != 0.0f && St.peakHz > 0.0f && D.style != D.peakStyle)
            {
                // RBJ peaking EQ
                const double A = std::pow(10.0, St.peakDb / 40.0), w0 = 2.0 * kPi * St.peakHz / sr_;
                const double alpha = std::sin(w0) / (2.0 * St.peakQ), c = std::cos(w0);
                const double a0 = 1.0 + alpha / A;
                D.pb0 = (float)((1.0 + alpha * A) / a0); D.pb1 = (float)((-2.0 * c) / a0); D.pb2 = (float)((1.0 - alpha * A) / a0);
                D.pa1 = (float)((-2.0 * c) / a0); D.pa2 = (float)((1.0 - alpha / A) / a0);
                D.peakOn = true; D.peakStyle = D.style;
            }
            else if (St.peakDb == 0.0f) { D.peakOn = false; D.peakStyle = -1; }
            D.rumble = St.rumble;
            D.dust = St.dust;

            // crossfader: x = how far the fader is open towards this deck (0 = closed end)
            float open = d == 0 ? 1.0f - xf : xf;
            if (ham) open = 1.0f - open;
            const float xg = xfShape(open, xc, lag);
            const float chan = getBool(P.chan) ? 1.0f : 0.0f;
            D.audibleTarget = chan * xg;
            D.gainTarget = chan * xg * mpc::dsp::dbToGain(get(P.vol)) * kStyleGain[D.style];
        }
        levelTarget_ = mpc::dsp::dbToGain(get(kLevel));
        crackle_ = get(kCrackle) * 0.01f;
        releaseMode_ = mpc::clamp(getInt(kRelease), 0, 2);
        timeoutRelease_ = releaseMode_ == 1;
        padBase_ = getInt(kPadBase) == 1 ? 37 : 36;

        // ---- the teacher ----
        teacher_.stepLen = sr_ * 60.0 / std::max(40.0f, get(kHBpm)) * 0.5;
        teacher_.click = getBool(kHClick);
        const int lessonP = mpc::clamp(getInt(kHLesson), 0, kNumLessons);   // 0 = basics tour, 1..6 = scratch lessons
        const int lesson = std::max(0, lessonP - 1);
        const bool wantDemo = getBool(kHDemo), wantRun = getBool(kHRun);
        if (lessonP == 0)
        {
            // the basics tour: UEBEN starts it, DEMO has nothing to show
            if (teacher_.running) stopLesson();
            if (wantDemo) setFromAudio(kHDemo, 0.0f);
            if (wantRun && !prevRun_) startTour();
            else if (!wantRun && tourActive_) tourActive_ = false;
            if (tourActive_) tourTick();
        }
        else
        {
            tourActive_ = false;
            if (wantDemo && !prevDemo_) { setFromAudio(kHRun, 0.0f); startLesson(lesson, true); }
            else if (wantRun && !prevRun_) { setFromAudio(kHDemo, 0.0f); startLesson(lesson, false); }
            else if (!wantDemo && !wantRun && teacher_.running) stopLesson();
            else if (teacher_.running && lesson != teacher_.lesson) startLesson(lesson, teacher_.demo);
        }
        prevDemo_ = getBool(kHDemo); prevRun_ = getBool(kHRun);
        liveHint_.store(lessonP == 0 ? std::min(tourStep_, kTourSteps) : 10 + lessonP);
        // the demo plays two bars, then it is your turn
        if (teacher_.running && teacher_.demo && teacher_.bar >= 2)
        {
            setFromAudio(kHDemo, 0.0f); setFromAudio(kHRun, 1.0f); prevDemo_ = false; prevRun_ = true;
            startLesson(lesson, false);
        }
        if (teacher_.running && teacher_.demo) stripEvent(teacher_.ghost, kSrcHelper);
    }

    // ---- the basics tour: each step waits until it was really done ----
    void startTour()
    {
        tourActive_ = true; tourStep_ = 0; tourFlips_ = 0; tourMove_ = 0.0; tourSign_ = 0;
        tourSlot_ = deck_[activeDeck_].cur;
        tourMsg_ = kMsgTour;
    }

    void tourTick()
    {
        const Deck& D = deck_[activeDeck_];
        bool done = false;
        switch (tourStep_)
        {
            case 0: done = D.motorOn; break;
            case 1: done = !D.motorOn; if (done) tourSlot_ = D.cur; break;
            case 2: done = D.cur != tourSlot_; break;
            case 3: done = D.handActive; break;
            case 4:
            {
                if (D.handActive)
                {
                    tourMove_ += std::fabs(D.handVel) * 128.0;
                    const int sg = D.handVel > 0.05 ? 1 : (D.handVel < -0.05 ? -1 : 0);
                    if (sg != 0 && sg != tourSign_) { if (tourSign_ != 0) ++tourFlips_; tourSign_ = sg; }
                }
                done = tourFlips_ >= 3 && tourMove_ > 0.4 * sr_;
                break;
            }
            case 5: done = !D.handActive; break;
            case 6: done = cutHeld_ || getBool(kCutLatch); break;
            case 7: done = get(kXFader) > 80.0f; break;
            case 8: done = activeDeck_ == 1; break;
            case 9: done = activeDeck_ == 0 && get(kXFader) < 20.0f; break;
            default: break;
        }
        if (done && tourStep_ < kTourSteps)
        {
            ++tourStep_;
            tourMsg_ = tourStep_ >= kTourSteps ? kMsgStars3 : kMsgGood;
            liveTour_.store(tourStep_);
        }
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
        markDirty(index);
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
            const bool platterIsMotor = platFollowOn_ && handSrc_ == kSrcJog && !(getInt(kCtrlProfile) == 1 && getInt(kPlatMode) == 0);
            if (platterIsMotor) { /* the real platter is the motor: the record stays where it is */ }
            // HAND: the platter only reports while it moves; 40 ms without a step = the hand has let go
            else if (platFollowOn_ && handSrc_ == kSrcJog && idleSamples_ > (int)(0.040 * sr_)) letGo(D);
            else if (timeoutSource && idleSamples_ > (int)(0.120 * sr_)) letGo(D);
            // AUTO: the MPC strip does not always send the centre when the finger leaves; a finger that stops
            // sending for 55 ms has left the strip (moving fingers report every few ms)
            else if (handSrc_ == kSrcPitchBend && releaseMode_ == 2 && idleSamples_ > (int)(0.055 * sr_)) letGo(D);
            // safety for strips that never spring back to the centre: 1 s without a value = hand off
            else if (idleSamples_ > (int)(1.0 * sr_)) letGo(D);
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
            D.slipX = D.x; D.slipVel = D.motorTarget != 0.0 ? D.vel : 0.0; D.slipValid = slipOn_;
        }
        handSrc_ = src;
        idleSamples_ = 0;
        releasePending_ = 0;
    }

    void letGo(Deck& D)
    {
        const bool helper = handSrc_ == kSrcHelper;
        D.handActive = false;
        if (&D == &deck_[activeDeck_]) { handSrc_ = kSrcNone; releasePending_ = 0; }
        if (D.live && getInt(kLiveSnap) == 0)
        {
            // LIVE + SOFORT ZURUECK: the track drops back in exactly where it is now, in time with the beat
            jumpTo(D, liveHead_ - liveLag_);
            const int d = &D == &deck_[0] ? 0 : 1;
            if (!D.motorOn) { setFromAudio(deckP_[d].play, 1.0f); refreshMotors(); }
            D.vel = liveRec_->sampleRate / sr_; D.catching = false; D.slipValid = false;
            return;
        }
        if (slipOn_ && D.slipValid)
        {
            // SLIP: the record carries on where it would be if you had never touched it
            const double pos = D.slipX;
            jumpTo(D, pos);
            D.vel = D.slipVel;
            D.catching = false;
            D.slipValid = false;
            return;
        }
        D.vel = D.handVel;                      // the record keeps the speed the hand gave it
        // AFTER SCRATCH = RUN ON: a stopped deck starts when you let go (the platter keeps turning, like a DJ deck)
        if (!D.motorOn && autoRun_ && !teacher_.running && !helper)
        {
            const int d = &D == &deck_[0] ? 0 : 1;
            setFromAudio(deckP_[d].play, 1.0f);
            refreshMotors();
        }
        D.catching = D.motorTarget != 0.0;      // ... the running motor grabs it with the CATCH time
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
            eventInterval_ += (mpc::clamp(dt, 0.0003 * sr_, 0.006 * sr_) - eventInterval_) * 0.3;   // glide at most 6 ms
        D.rawTarget = raw;
        const double glide = (dt > 0.0 && dt < 0.025 * sr_) ? std::max(1.0, eventInterval_) : 1.0;
        D.interpLeft = (int)std::lround(glide);
        D.interpStep = (D.rawTarget - D.handTarget) / (double)D.interpLeft;
    }

    // ---- Denon SC6000M (computer mode), decoded from the user's log 2026-11-18:
    //  platter: every ~1 ms  B0 11/31 (14-bit position counter), B0 37/36 (signed 14-bit movement), E0 (unused);
    //           3600 steps per turn (Denon spec), motor forward = negative steps; nothing is sent while it stands
    //  pitch fader CC8/CC40 (14 bit, top = 127 = minus), PLAY = note 1, CUE = note 2, pads 1-8 = notes 32-39,
    //  all keys send note on 127 / note off 64. Layer A = channel 1, layer B = channel 2.
    bool scEvent(const mpc::MidiEvent& ev)
    {
        if (getInt(kCtrlProfile) != 1) return false;
        const int ch = ev.channel();
        if (ch > 1) return false;
        const int layer = ch;
        // the SC6000M sends pitch bend only together with its platter frames: swallow it only then, so the MPC's
        // own touch strip (pitch bend too) keeps working
        if (ev.isPitchBend()) return eventClock_ - scSeenClock_ < 0.05 * sr_;
        if (ev.isController())
        {
            const int cc = ev.data[1];
            if (cc == 17 || cc == 49 || cc == 54 || cc == 55) scSeenClock_ = eventClock_;
            if (cc == 17 || cc == 49) return true;                          // position counter: not needed
            if (cc == 54 || cc == 55) return platterEvent(ev) || true;      // movement: the platter (when followed)
            if (cc == 8) { scPitchMsb_[layer] = ev.data[2]; return true; }
            if (cc == 40)
            {
                const int v = scPitchMsb_[layer] * 128 + ev.data[2];
                const float pct = mpc::clamp((float)(8192 - v) / 8192.0f * 100.0f, -100.0f, 100.0f);
                setFromAudio(deckP_[layer].pitch, std::fabs(pct) < 0.6f ? 0.0f : pct);   // small dead zone at the centre
                return true;
            }
            return cc == 3 || cc == 6 || cc == 7;                           // encoders / strip: not mapped yet
        }
        const bool on = ev.isNoteOn() && ev.data[2] == 127, off = ev.isNoteOff() && (ev.data[2] == 64 || ev.status() == 0x80);
        if (!on && !off) return false;
        const int n = ev.note();
        const bool scKey = n <= 30 || (n >= 32 && n <= 39) || n == 52 || n == 53;
        if (!scKey) return false;
        if (!on) return true;
        if (n == 1)                                                          // PLAY: start / stop the deck
        {
            setFromAudio(deckP_[layer].play, getBool(deckP_[layer].play) ? 0.0f : 1.0f);
            refreshMotors();
        }
        else if (n == 2)                                                     // CUE: back to the start of the record
        {
            if (layer == activeDeck_) jumpTo(deck_[layer], 0.0);
            else { deck_[layer].x = 0.0; }
        }
        else if (n >= 32 && n <= 39)                                         // pads 1-8: the 8 records of this deck
        {
            setFromAudio(deckP_[layer].slot, (float)(n - 32));
            if (layer != activeDeck_) setFromAudio(kDeck, (float)layer);
        }
        return true;
    }

    // every message key the controller sent during the test (status byte incl. channel x number)
    std::atomic<uint32_t> ctrlSeen_[1024] = {};
    bool ctrlKnown(const mpc::MidiEvent& ev) const
    {
        const int st = ev.data[0], n = ev.isPitchBend() || ev.status() == 0xD0 ? 0 : (ev.data[1] & 0x7F);
        const int bit = ((st & 0x7F) << 7 | n) & 32767;
        const int stn = st == 0x80 + (st & 15) ? 0x90 + (st & 15) : st;     // a note off counts as its note
        const int bit2 = ((stn & 0x7F) << 7 | n) & 32767;
        return ((ctrlSeen_[bit >> 5].load(std::memory_order_relaxed) >> (bit & 31)) & 1u) ||
               ((ctrlSeen_[bit2 >> 5].load(std::memory_order_relaxed) >> (bit2 & 31)) & 1u);
    }

    // the learned platter: every message is a step of the real record -> the deck follows it exactly
    bool platterEvent(const mpc::MidiEvent& ev)
    {
        if (!platFollowOn_) return false;
        const int kind = platDec_.kind.load(std::memory_order_relaxed);
        if (kind == skr::PlatterDecoder::kNone) return false;
        const int st = ev.status(), ch = ev.channel(), base = platDec_.baseCh.load(std::memory_order_relaxed);
        if (st != platDec_.status.load(std::memory_order_relaxed) || (ch != base && ch != base + 1)) return false;
        const int d1 = platDec_.d1.load(std::memory_order_relaxed);
        const int layer = ch - base;
        double counts = 0.0;
        if (kind == skr::PlatterDecoder::kAbs14Pb)
        {
            const int v = ev.pitchBend() + 8192;
            if (platLast_[layer] >= 0) { int d = v - platLast_[layer]; if (d > 8192) d -= 16384; else if (d < -8192) d += 16384; counts = d; }
            platLast_[layer] = v;
        }
        else if (kind == skr::PlatterDecoder::kVel14)
        {
            // SC6000M: CC55 = high byte, CC54 = low byte of the signed movement since the last frame (1 kHz)
            if (ev.data[1] == 55) { platMsb_[layer] = ev.data[2]; return true; }
            if (ev.data[1] != 54) return false;
            int v = platMsb_[layer] * 128 + ev.data[2];
            if (v >= 8192) v -= 16384;
            counts = v;
        }
        else
        {
            if (ev.data[1] != d1 && !(kind == skr::PlatterDecoder::kAbs14Cc && ev.data[1] == d1 + 32)) return false;
            const int v = ev.data[2];
            if (kind == skr::PlatterDecoder::kRel64) counts = v - 64;
            else if (kind == skr::PlatterDecoder::kRel2c) counts = v < 64 ? v : v - 128;
            else if (kind == skr::PlatterDecoder::kAbs7)
            {
                if (platLast_[layer] >= 0) { int d = v - platLast_[layer]; if (d > 64) d -= 128; else if (d < -64) d += 128; counts = d; }
                platLast_[layer] = v;
            }
            else   // 14 bit from MSB + LSB: act on the LSB (sent second)
            {
                if (ev.data[1] == d1) { platMsb_[layer] = v; return true; }
                const int full = platMsb_[layer] * 128 + v;
                if (platLast_[layer] >= 0) { int d = full - platLast_[layer]; if (d > 8192) d -= 16384; else if (d < -8192) d += 16384; counts = d; }
                platLast_[layer] = full;
            }
        }
        if (layer != activeDeck_) { setFromAudio(kDeck, (float)layer); return true; }   // layer switched on the SC6000M
        const double turns = counts * (double)platDec_.turnsPerCount.load(std::memory_order_relaxed);
        platTurns_.store(platTurns_.load(std::memory_order_relaxed) + turns, std::memory_order_relaxed);
        // the real platter's speed is the reference: 1 turn at 33 1/3 (or 45) = exactly the record at normal speed,
        // whatever turntable is chosen in the plugin
        Deck& D = deck_[activeDeck_];
        const Record* rec = recOf(D);
        const double platRpm = getInt(kPlatRpm) == 1 ? 45.0 : 100.0 / 3.0;
        double pitchMul = 1.0;
        if (getInt(kCtrlProfile) == 1 && getInt(kPlatMode) == 1)
        {
            static const double ranges[3] = {0.08, 0.16, 0.50};
            const DeckParams& P = deckP_[activeDeck_];
            pitchMul = 1.0 + get(P.pitch) * 0.01 * ranges[mpc::clamp(getInt(P.prange), 0, 2)];
        }
        const double samples = turns * pitchMul * 60.0 / platRpm * (rec != nullptr ? rec->sampleRate : sr_);
        const double deckTurns = D.samplesPerRev > 1.0 ? samples / D.samplesPerRev : 0.0;
        if (turns != 0.0) jogEvent(deckTurns);
        else idleSamples_ = 0;      // a held, still platter: keep holding the record
        return true;
    }

    void handleMidi(const mpc::MidiEvent& ev)
    {
        Deck& D = deck_[activeDeck_];
        if (ev.isPitchBend())
        {
            const int pb = ev.pitchBend();
            if (pb == 0)
            {
                if (D.handActive && handSrc_ == kSrcPitchBend && !timeoutRelease_) releasePending_ = (int)(0.008 * sr_);
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

    // PADS (the screen shows the same 4 x 4 map):
    //   top row      13 DECK A   14 DECK B   15 REVERSE   16 SLIP
    //   row 3         9 CUT      10 HOLD     11 CUE       12 START/STOP
    //   rows 1 + 2    1..8  the 8 samples of the active deck (5-8 above 1-4)
    // HOLD + CUE stores the cue point (hand on the record, find the spot, tap CUE).
    // BATTLE layout: the pads are split and mirrored, left half = deck A, right half = deck B
    //   top      A: START  DECK  |  DECK  START :B
    //            A: CUT    CUE   |  CUE   CUT   :B
    //            A: S3     S4    |  S4    S3    :B
    //   bottom   A: S1     S2    |  S2    S1    :B
    void handlePadBattle(int f, bool on)
    {
        const int row = f / 4, col = f % 4;
        const int d = col < 2 ? 0 : 1;
        const int inner = d == 0 ? col : 3 - col;          // 0 = outer column, 1 = inner column
        Deck& D = deck_[d];
        const DeckParams& P = deckP_[d];
        if (row <= 1) { if (on) fire(d, row * 2 + inner, true); return; }
        if (row == 2)
        {
            if (inner == 0) { if (on) { cutHeld_ = true; cutDeck_ = d; } else if (cutDeck_ == d) cutHeld_ = false; }
            else { cueHeld_ = on; if (on) { jumpTo(D, D.cue[D.cur]); cueFlash_ = (int)(0.15 * sr_); } }
        }
        else
        {
            if (inner == 0) { if (on) setFromAudio(P.play, getBool(P.play) ? 0.0f : 1.0f); }
            else if (on && activeDeck_ != d) setFromAudio(kDeck, (float)d);
        }
        readLater_ = true;
    }

    void handlePad(int f, bool on)
    {
        if (layout_ == 1) { handlePadBattle(f, on); return; }
        const int d = activeDeck_;
        Deck& D = deck_[d];
        const DeckParams& P = deckP_[d];
        if (f < kSlots) { if (on) fire(d, f, true); return; }
        switch (f)
        {
            case 8:  if (on) { cutHeld_ = true; cutDeck_ = d; } else cutHeld_ = false; break;
            case 9:
                if (on) { padHold_ = true; grab(kSrcPad); anchorSrc_ = kSrcPad; D.rawTarget = D.handTarget = D.x; D.interpLeft = 0; }
                else { padHold_ = false; if (D.handActive && handSrc_ == kSrcPad) letGo(D); }
                break;
            case 10:
                cueHeld_ = on;
                if (on)
                {
                    if (padHold_) { D.cue[D.cur] = D.x; cueFlash_ = (int)(0.3 * sr_); }   // HOLD + CUE = set cue
                    else jumpTo(D, D.cue[D.cur]);
                }
                break;
            case 11: if (on) setFromAudio(P.play, getBool(P.play) ? 0.0f : 1.0f); break;
            case 12: if (on && d != 0) setFromAudio(kDeck, 0.0f); break;
            case 13: if (on && d != 1) setFromAudio(kDeck, 1.0f); break;
            case 14: if (on) setFromAudio(P.reverse, getBool(P.reverse) ? 0.0f : 1.0f); break;
            case 15: if (on) setFromAudio(kSlip, getBool(kSlip) ? 0.0f : 1.0f); break;
            default: break;
        }
        readLater_ = true;
    }

    void jumpTo(Deck& D, double pos)
    {
        const Record* r = recOf(D);
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
            float outL = 0.0f, outR = 0.0f, retL = 0.0f, retR = 0.0f;
            for (int d = 0; d < 2; ++d)
            {
                Deck& D = deck_[d];
                stepDeck(D);
                // CUT pad / teacher demo
                float cutTarget = 1.0f;
                if (teacher_.running && teacher_.demo && d == activeDeck_) cutTarget = teacher_.faderTarget ? 1.0f : 0.0f;
                else
                {
                    const bool held = (cutHeld_ && cutDeck_ == d) || (cutLatchOn_ && cutLatchDeck_ == d);
                    if (cutOpenMode_ && d == activeDeck_) cutTarget = held ? 1.0f : 0.0f;
                    else if (held) cutTarget = 0.0f;
                }
                if (D.cutGain < cutTarget) D.cutGain = std::min(cutTarget, D.cutGain + cutStep_);
                else if (D.cutGain > cutTarget) D.cutGain = std::max(cutTarget, D.cutGain - cutStep_);
                D.gain += (D.gainTarget - D.gain) * gainCoef;
                D.audible += (D.audibleTarget - D.audible) * gainCoef;
                const float g = D.gain * D.cutGain;
                if (g < 1e-6f) { D.xfade = 0.0f; D.xOldRec = nullptr; continue; }   // closed: nothing to hear
                float sl = 0.0f, sr = 0.0f;
                readDeck(D, sl, sr, xfadeStep);
                if (retOn_ && d == liveDeck_) { retL += sl * g; retR += sr * g; }   // back to the track via FEED
                else { outL += sl * g; outR += sr * g; }
            }

            // teacher: watches the active deck, ticks the click
            if (teacher_.running)
            {
                const Record* r = recOf(act);
                const bool aud = act.audible * act.cutGain > 0.5f;
                const float c = teacher_.tick(act.x, act.vel, act.handActive && handSrc_ != kSrcHelper, aud, act.motorOn, act.stripScale, r != nullptr, sr_);
                if (teacher_.tempoUp) { teacher_.tempoUp = false; setFromAudio(kHBpm, std::min(110.0f, get(kHBpm) + 6.0f)); }
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
            // DC blocker (3 Hz): a record held still at a crest must not leave a constant offset on the output
            { const float yl = ol - dcXl_ + 0.9996f * dcYl_; dcXl_ = ol; dcYl_ = yl; ol = yl;
              const float yr = orr - dcXr_ + 0.9996f * dcYr_; dcXr_ = orr; dcYr_ = yr; orr = yr; }
            ol = safetyClip(ol); orr = safetyClip(orr);   // never over 0 dBFS, transparent below -1 dBFS
            if (retOn_)
            {
                const uint32_t k = (uint32_t)((liveHeadU_ + (uint64_t)i) & skrfeed::kRetMask);
                // unity: the track keeps its own level when it goes LIVE (SKRATCHA's Level is for SKRATCHA's track)
                liveFeed_->ret[2 * k] = safetyClip(mpc::dsp::sanitize(retL));
                liveFeed_->ret[2 * k + 1] = safetyClip(mpc::dsp::sanitize(retR));
            }
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
            if (D.slipValid)
            {
                const double target = D.motorTarget * (1.0 + D.wowNow);
                if (D.slipVel < target) D.slipVel = std::min(target, D.slipVel + D.startStep);
                else if (D.slipVel > target) D.slipVel = std::max(target, D.slipVel - D.brakeStep);
                D.slipX += D.slipVel;
            }
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
        if (D.live) clampLive(D);
        const Record* rec = recOf(D);
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
        // loudness of the dry record (weighted: presence counts more, like the ear)
        {
            const float m = 0.5f * (sl + sr);
            D.agHd += (m - D.agHd) * agHpCoef_;
            const float w = m + 1.5f * (m - D.agHd);
            D.agDry += (w * w - D.agDry) * agCoef_;
        }
        // era tone: mono, high pass, resonance, saturation, then the low pass below
        if (D.mono) { const float m = 0.5f * (sl + sr); sl = sr = m; }
        if (D.hpCoef > 0.0f)
        {
            D.hpL += (sl - D.hpL) * D.hpCoef; D.hpR += (sr - D.hpR) * D.hpCoef;
            sl -= D.hpL; sr -= D.hpR;
        }
        if (D.peakOn)
        {
            float* zl = D.pz[0]; const float yl = D.pb0 * sl + zl[0]; zl[0] = D.pb1 * sl - D.pa1 * yl + zl[1]; zl[1] = D.pb2 * sl - D.pa2 * yl; sl = yl;
            float* zr = D.pz[1]; const float yr = D.pb0 * sr + zr[0]; zr[0] = D.pb1 * sr - D.pa1 * yr + zr[1]; zr[1] = D.pb2 * sr - D.pa2 * yr; sr = yr;
        }
        if (D.drive > 0.0f)
        {
            const float k = 1.0f + D.drive * 4.0f;
            sl = softClip(sl * k) * D.driveNorm; sr = softClip(sr * k) * D.driveNorm;
        }
        // low pass (old cartridges and speakers), bearing rumble while the platter turns
        if (D.lpCoef < 1.0f)
        {
            D.lpL += (sl - D.lpL) * D.lpCoef; D.lpR += (sr - D.lpR) * D.lpCoef;
            D.lp2L += (D.lpL - D.lp2L) * D.lpCoef; D.lp2R += (D.lpR - D.lp2R) * D.lpCoef;
            sl = D.lp2L; sr = D.lp2R;
        }
        // auto gain: the coloured record plays exactly as loud as the dry one, whatever the era
        {
            const float m = 0.5f * (sl + sr);
            D.agHw += (m - D.agHw) * agHpCoef_;
            const float w = m + 1.5f * (m - D.agHw);
            D.agWet += (w * w - D.agWet) * agCoef_;
            if (++D.agCount >= 64)
            {
                D.agCount = 0;
                if (D.agDry > 1e-7f && D.agWet > 1e-9f) D.agTarget = mpc::clamp(std::sqrt(D.agDry / D.agWet), 0.3f, 2.8f);
            }
            D.ag += (D.agTarget - D.ag) * agSmooth_;
            sl *= D.ag; sr *= D.ag;
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
        // surface hiss of shellac / old vinyl while the record turns
        if (D.hiss > 0.0f && motion > 0.01f)
        {
            D.rng = D.rng * 1664525u + 1013904223u;
            const float n = ((float)(D.rng >> 8) * (1.0f / 8388608.0f)) - 1.0f;
            const float h = n * D.hiss * std::sqrt(motion);
            sl += h; sr += h * 0.9f;
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

    static float safetyClip(float x)
    {
        const float a = std::fabs(x);
        if (a <= 0.89f) return x;
        const float y = 0.89f + 0.11f * std::tanh((a - 0.89f) / 0.11f);
        return x < 0.0f ? -y : y;
    }

    static float softClip(float x) { if (x > 3.0f) return 1.0f; if (x < -3.0f) return -1.0f; return x * (27.0f + x * x) / (27.0f + 9.0f * x * x); }

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
                bump(deckP_[d].names + s); bump(deckP_[d].name); bump(kANames + s); bump(kCName);
                if (d == 0 && s < 4) bump(kAFix + s);
                if (d == 1) bump(kBNames + s);
                if (!all) return;   // one load per pass keeps the reporter responsive
            }
    }

    void bump(int index) { bumps_[index >> 6].fetch_or(1ull << (index & 63)); }

    std::string selectedPath()
    {
        std::lock_guard<std::mutex> lk(textMutex_);
        const int i = getInt(kBrFile) - 1;
        if (i < 0 || i >= (int)files_.size() || filesDir_.empty()) return std::string();
        return filesDir_ + "/" + files_[(size_t)i];
    }

    // ---- the drive browser: a real folder tree over every drive of the MPC ----
    struct DirEntry { std::string name, path; int kind = 1; };    // kind 0 = up, 1 = folder, 2 = drive / root

    static bool isDir(const std::string& p)
    {
#if defined(_WIN32)
        (void)p; return false;
#else
        struct stat st; return stat(p.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
#endif
    }

    static std::vector<std::string> subDirs(const std::string& path)
    {
        std::vector<std::string> out;
#if !defined(_WIN32)
        if (DIR* d = opendir(path.c_str()))
        {
            while (dirent* e = readdir(d))
            {
                const std::string n = e->d_name;
                if (n.empty() || n[0] == '.' || n == "lost+found" || n == "System Volume Information" || n == "$RECYCLE.BIN") continue;
                if (path == "/" && (n == "proc" || n == "sys" || n == "dev")) continue;
                bool dir = e->d_type == DT_DIR;
                if (e->d_type == DT_UNKNOWN || e->d_type == DT_LNK) dir = isDir(path + (path == "/" ? "" : "/") + n);
                if (dir) out.push_back(n);
                if ((int)out.size() >= kMaxEntries - 1) break;
            }
            closedir(d);
        }
#endif
        std::sort(out.begin(), out.end(), lessNoCase);
        return out;
    }

    std::vector<DirEntry> roots()
    {
        std::vector<DirEntry> r;
        auto add = [&](const std::string& label, const std::string& path)
        {
            if (path.empty() || !isDir(path)) return;
            for (const DirEntry& e : r) if (e.path == path) return;
            DirEntry e; e.name = label; e.path = path; e.kind = 2; r.push_back(e);
        };
        add("SKRATCHA SAMPLES", builtInDir_);
        const std::string pf = mpc::pluginFolder();
        if (!pf.empty()) add("MY SAMPLES (PLUGIN)", pf + "/My Samples");
#if !defined(_WIN32)
        for (const char* pat : {"/media/*", "/mnt/*", "/run/media/*/*", "/storage/*", "/Volumes/*"})
        {
            glob_t g;
            if (glob(pat, 0, nullptr, &g) == 0)
            {
                for (size_t i = 0; i < g.gl_pathc; ++i)
                {
                    std::string p = g.gl_pathv[i], n = fileOf(p);
                    for (char& ch : n) ch = (char)std::toupper((unsigned char)ch);
                    add("LAUFWERK " + n, p);
                }
                globfree(&g);
            }
        }
        add("INTERNE SSD (NVME)", "/nvme");
        add("SD-KARTE", "/sdcard");
        add("MPC CONTENT", "/usr/share/Akai/Content");
        add("SYSTEM - ALLES (/)", "/");
#endif
        return r;
    }

    bool isRootPath(const std::string& p)
    {
        for (const std::string& r : rootPaths_) if (r == p) return true;
        return false;
    }

    // scanner thread: list the current folder (or the drives) and the files of the selected folder
    void listCurrent()
    {
        listing_.store(true);
        for (int r = 0; r < 7; ++r) bump(kDRows + r);
        std::string cwd;
        { std::lock_guard<std::mutex> lk(textMutex_); cwd = cwd_; }
        std::vector<DirEntry> list;
        if (cwd.empty())
        {
            list = roots();
            std::vector<std::string> rp; for (const DirEntry& e : list) rp.push_back(e.path);
            std::lock_guard<std::mutex> lk(textMutex_);
            rootPaths_ = rp;
        }
        else
        {
            DirEntry up; up.kind = 0; up.name = ".."; up.path = cwd; list.push_back(up);
            for (const std::string& n : subDirs(cwd))
            {
                DirEntry e; e.name = n; e.path = cwd + (cwd == "/" ? "" : "/") + n; e.kind = 1;
                list.push_back(e);
            }
        }
        {
            std::lock_guard<std::mutex> lk(textMutex_);
            dirs_ = std::move(list);
            numFolders_.store((int)dirs_.size());
        }
        dirsVersion_.fetch_add(1);
        listing_.store(false);
        bumpBrowser(); bump(kBrPath);
        filesReq_.store(true);
    }

    // the sounds of the chosen folder; with "Sub Folders" also every sound below it (depth 8, 4000 files),
    // shown while the search runs and stopped as soon as another folder is chosen
    void listFiles()
    {
        std::string path;
        bool deep;
        { std::lock_guard<std::mutex> lk(textMutex_); path = filesWant_; }
        deep = getBool(kSubFolders);
        filesDeep_ = deep;
        std::vector<std::string> names;
        auto publish = [&](bool searching)
        {
            {
                std::lock_guard<std::mutex> lk(textMutex_);
                files_ = names;
                filesDir_ = path;
                numFiles_.store((int)files_.size());
                filesSearching_ = searching;
            }
            filesVersion_.fetch_add(1);
            for (int r = 0; r < 7; ++r) bump(kFRows + r);
            bump(kBrInfo);
        };
        if (path.empty()) { publish(false); return; }
        std::vector<std::string> here;
        listWavs(path, here);
        for (const std::string& w : here) { names.push_back(fileOf(w)); if ((int)names.size() >= kMaxEntries) break; }
        if (!deep || path == "/") { publish(false); return; }
        publish(true);
        // breadth first, so the nearest folders come first
        std::vector<std::pair<std::string, int>> queue;   // relative path, depth
        for (const std::string& d : subDirs(path)) queue.push_back({d, 1});
        auto lastPub = std::chrono::steady_clock::now();
        size_t shown = names.size();
        for (size_t qi = 0; qi < queue.size() && (int)names.size() < kMaxEntries; ++qi)
        {
            if (filesReq_.load() || listReq_.load() || stopThread_.load()) return;   // the user chose something else
            const std::string rel = queue[qi].first;
            const int depth = queue[qi].second;
            std::vector<std::string> found;
            listWavs(path + "/" + rel, found);
            for (const std::string& w : found) { names.push_back(rel + "/" + fileOf(w)); if ((int)names.size() >= kMaxEntries) break; }
            if (depth < 8 && queue.size() < 20000)
                for (const std::string& d : subDirs(path + "/" + rel)) queue.push_back({rel + "/" + d, depth + 1});
            const auto now = std::chrono::steady_clock::now();
            if (names.size() != shown && now - lastPub > std::chrono::milliseconds(250)) { shown = names.size(); publish(true); lastPub = now; }
        }
        publish(false);
    }

    void bumpBrowser()
    {
        for (int r = 0; r < 7; ++r) { bump(kDRows + r); bump(kFRows + r); }
        bump(kBrInfo); bump(kBrFolderName); bump(kBrPath);
    }

    static void lowPriority()
    {
#if defined(__linux__)
        setpriority(PRIO_PROCESS, (id_t)syscall(SYS_gettid), 4);    // a little below the UI; audio runs real-time anyway
#endif
    }

    // ---- thread 1: the drive scanner (slow, low priority) ----
    void scanLoop()
    {
        listCurrent();
        while (!stopThread_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            if (rescanRequested_.exchange(false)) { listReq_.store(true); rescanDone_.store(true); }
            if (listReq_.exchange(false)) listCurrent();
            if (filesReq_.exchange(false)) listFiles();
        }
    }

    // ---- thread 2: loads samples into slots and the preview, deletes replaced ones (low priority) ----
    void loaderLoop()
    {
        lowPriority();
        std::string previewPath;
        bool previewWasOn = false;
        while (!stopThread_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            for (int d = 0; d < 2; ++d) for (int s = 0; s < kSlots; ++s) delete retired_[d][s].exchange(nullptr);
            delete previewRetired_.exchange(nullptr);
            loadWantedSlots(false);
            logService();
            RecJob* job = nullptr;
            { std::lock_guard<std::mutex> lk(recJobMutex_); job = recJob_; recJob_ = nullptr; }
            if (job != nullptr) { finishRecording(*job); delete job; }
            const bool pv = getBool(kBrPreview);
            if (pv)
            {
                const std::string p = selectedPath();
                if ((!previewWasOn || p != previewPath) && previewPending_.load() == nullptr && previewRetired_.load() == nullptr)
                {
                    previewPath = p;
                    if (Record* r = p.empty() ? nullptr : loadRecord(p, 20.0)) previewPending_.store(r);
                }
            }
            else previewPath.clear();
            previewWasOn = pv;
        }
    }

    // ---- 2.5: MIDI monitor and the guided controller test (reporter thread) ----
    struct MonState
    {
        bool on = false;
        int step = 0, ticksInStep = 0;
        float lastNext = 0.0f, lastPrev = 0.0f;
        uint64_t total = 0, secCount = 0, perSec = 0, t0 = 0;
        int secTick = 0;
        std::vector<skr::KeyStat> stats;          // this step
        std::vector<int> lastMsb;                 // per channel * 32 controllers
        std::vector<int> lastFull;
        uint64_t keyFirst = 0, keyLast = 0;
        std::string lines[8];
        bool linesDirty = false;
        double lastTurns = 0.0;
        std::chrono::steady_clock::time_point lastSpeedT = std::chrono::steady_clock::now();
    } mon_;

    void logAppend(const std::string& s)
    {
        std::lock_guard<std::mutex> lk(logMutex_);
        if (logPending_.size() < (8u << 20)) logPending_ += s;
    }

    static std::string hex2(int v) { char b[4]; std::snprintf(b, sizeof(b), "%02X", v & 0xFF); return b; }

    skr::KeyStat& statOf(int key)
    {
        for (skr::KeyStat& k : mon_.stats) if (k.key == key) return k;
        mon_.stats.emplace_back(); mon_.stats.back().key = key;
        return mon_.stats.back();
    }

    void stepSummary()
    {
        std::vector<const skr::KeyStat*> v;
        for (const skr::KeyStat& k : mon_.stats) v.push_back(&k);
        std::sort(v.begin(), v.end(), [](const skr::KeyStat* a, const skr::KeyStat* b) { return a->count > b->count; });
        std::string out = "### ZUSAMMENFASSUNG SCHRITT " + std::to_string(mon_.step) + "  (" + std::to_string(mon_.ticksInStep * 15 / 1000) + " s)\n";
        for (size_t i = 0; i < v.size() && i < 40; ++i)
        {
            const skr::KeyStat& k = *v[i];
            int lo = 127, hi = 0, distinct = 0;
            for (int x = 0; x < 128; ++x) if (k.hist[x]) { lo = std::min(lo, x); hi = std::max(hi, x); ++distinct; }
            const int st = (k.key >> 8) & 0xFF, d1 = k.key & 0x7F;
            char b[200];
            std::snprintf(b, sizeof(b), "###   %02X %02X  CH%-2d %-9s %3d  ANZAHL %6d  WERTE %3d..%3d (%3d VERSCHIEDEN)  REL64 %lld  REL2C %lld  ABS %lld  PB %lld\n",
                          st, d1, (st & 15) + 1, skr::midiTypeName((uint8_t)st), d1, k.count, lo, hi, distinct, k.rel64, k.rel2c, k.absWrap, k.pbWrap);
            out += b;
        }
        logAppend(out);
    }

    // learn the platter from a step where it turned a known amount
    bool learnPlatter(double expectedTurns, bool perSecond)
    {
        if (getInt(kCtrlProfile) == 1) return true;      // the SC6000M profile is fixed, nothing to learn
        const skr::KeyStat* best = nullptr;
        for (const skr::KeyStat& k : mon_.stats)
        {
            const int type = (k.key >> 8) & 0xF0;
            if (type != 0xB0 && type != 0xE0 && type != 0x90) continue;
            if (k.changes < 15 || k.count < 20) continue;
            if (best == nullptr || k.count > best->count) best = &k;
        }
        if (best == nullptr) { platInfo_ = "TELLER: KEINE DREH-DATEN"; bump(kPlatInfo); logAppend("### TELLER: keine passenden Daten gefunden\n"); return false; }
        const int st = (best->key >> 8) & 0xFF, type = st & 0xF0, d1 = best->key & 0x7F;
        int kind;
        long long counts;
        if (type == 0xE0) { kind = skr::PlatterDecoder::kAbs14Pb; counts = best->pbWrap; }
        else
        {
            int nearMid = 0, nearEdge = 0;
            for (int x = 0; x < 128; ++x) { if (std::abs(x - 64) <= 16) nearMid += best->hist[x]; if ((x >= 1 && x <= 31) || x >= 97) nearEdge += best->hist[x]; }
            const skr::KeyStat* lsb = nullptr;
            if (type == 0xB0 && d1 < 32) for (const skr::KeyStat& k : mon_.stats) if (k.key == ((st << 8) | (d1 + 32)) && k.count * 2 > best->count) lsb = &k;
            if (lsb != nullptr) { kind = skr::PlatterDecoder::kAbs14Cc; counts = lsb->pbWrap; }
            else if (nearMid > best->count * 0.9) { kind = skr::PlatterDecoder::kRel64; counts = best->rel64; }
            else if (nearEdge > best->count * 0.9) { kind = skr::PlatterDecoder::kRel2c; counts = best->rel2c; }
            else { kind = skr::PlatterDecoder::kAbs7; counts = best->absWrap; }
        }
        double turns = expectedTurns;
        if (perSecond)
        {
            const double secs = (double)(mon_.keyLast - mon_.keyFirst) / sr_;
            turns = expectedTurns * std::max(0.5, secs);
        }
        if (std::llabs(counts) < 8) { platInfo_ = "TELLER: ZU WENIG BEWEGUNG"; bump(kPlatInfo); return false; }
        platDec_.status.store(type); platDec_.d1.store(d1); platDec_.baseCh.store(st & 15);
        platDec_.turnsPerCount.store((float)(turns / (double)counts));
        platDec_.kind.store(kind);
        static const char* kn[] = {"-", "REL", "REL2", "ABS", "PB14", "CC14"};
        const double cpr = std::fabs((double)counts / turns);
        platInfo_ = "ERKANNT: CH" + std::to_string((st & 15) + 1) + " " + (type == 0xE0 ? std::string("PB") : (type == 0x90 ? "N" : "CC") + std::to_string(d1)) +
                    " " + kn[kind] + " " + std::to_string((int)std::lround(cpr)) + "/U";
        bump(kPlatInfo);
        logAppend("### TELLER ERKANNT: " + platInfo_ + fmt("  counts %.0f", (double)counts) + fmt("  turns %.3f", turns) + "\n");
        return true;
    }

    void setStep(int st)
    {
        mon_.step = mpc::clamp(st, 0, skr::kNumTestSteps - 1);
        mon_.ticksInStep = 0;
        mon_.stats.clear();
        mon_.keyFirst = mon_.keyLast = 0;
        set(kMidiStep, (float)mon_.step);
        if (effect_ != nullptr && host_ != nullptr) notifyHostParameterChanged(kMidiStep);
        const skr::TestStep& t = skr::kTestSteps[mon_.step];
        { std::lock_guard<std::mutex> lk(textMutex_); midiTxt_[0] = t.l1; midiTxt_[1] = t.l2; }
        bump(kMidiT1); bump(kMidiT2);
        if (mon_.on) logAppend(std::string("\n### SCHRITT ") + std::to_string(mon_.step) + ": " + t.l1 + " / " + t.l2 + "\n");
    }

    void midiReporter(int tick)
    {
        (void)tick;
        const bool on = getBool(kMidiMon);
        if (on && !mon_.on)
        {
            mon_ = MonState(); mon_.on = true;
            mon_.lastNext = getNormalised(kMidiNext); mon_.lastPrev = getNormalised(kMidiPrev);
            mon_.lastMsb.assign(16 * 32, 0); mon_.lastFull.assign(16 * 32, -1);
            { std::lock_guard<std::mutex> lk(logMutex_); logOpenWanted_ = true; logCloseWanted_ = false; logPending_.clear(); }
            char hdr[256];
            const std::time_t now = std::time(nullptr);
            std::strftime(hdr, sizeof(hdr), "SKRATCHA 2.5 MIDI-PROTOKOLL  %Y-%m-%d %H:%M:%S\n", std::localtime(&now));
            logAppend(std::string(hdr) + "Zeit(s)      Bytes     Kanal Typ        Nr  Wert\n");
            setStep(1);
        }
        else if (!on && mon_.on)
        {
            stepSummary();
            logAppend("### TEST BEENDET\n");
            mon_.on = false;
            { std::lock_guard<std::mutex> lk(logMutex_); logCloseWanted_ = true; }
            setStep(0);
        }
        if (mon_.on)
        {
            if (getNormalised(kMidiNext) != mon_.lastNext)
            {
                mon_.lastNext = getNormalised(kMidiNext);
                stepSummary();
                if (mon_.step == 2) learnPlatter(getInt(kPlatRpm) == 1 ? 0.75 : 33.3333 / 60.0, true);
                if (mon_.step == 7 && platDec_.kind.load() == skr::PlatterDecoder::kNone) learnPlatter(1.0, false);
                if (mon_.step < skr::kNumTestSteps - 1) setStep(mon_.step + 1);
            }
            if (getNormalised(kMidiPrev) != mon_.lastPrev) { mon_.lastPrev = getNormalised(kMidiPrev); stepSummary(); setStep(std::max(1, mon_.step - 1)); }
            ++mon_.ticksInStep;
        }
        // drain the ring
        skr::MidiRec r;
        std::string logChunk;
        int n = 0;
        while (midiRing_.pop(r) && n < 4000)
        {
            ++n; ++mon_.total; ++mon_.secCount;
            if (mon_.t0 == 0) mon_.t0 = r.clock + 1;
            const int st = r.b[0], d1 = r.b[1] & 0x7F, d2 = r.b[2] & 0x7F, type = st & 0xF0, ch = st & 15;
            char line[96];
            if (type == 0xE0)
                std::snprintf(line, sizeof(line), "CH%-2d PB %+5d", ch + 1, (d2 * 128 + d1) - 8192);
            else
                std::snprintf(line, sizeof(line), "CH%-2d %-9s %3d = %3d", ch + 1, skr::midiTypeName((uint8_t)st), d1, d2);
            for (int i = 7; i > 0; --i) mon_.lines[i] = mon_.lines[i - 1];
            mon_.lines[0] = hex2(st) + " " + hex2(d1) + " " + hex2(d2) + "  " + line;
            mon_.linesDirty = true;
            if (!mon_.on) continue;
            char lg[128];
            std::snprintf(lg, sizeof(lg), "%11.5f  %02X %02X %02X  %s\n", (double)(r.clock - (mon_.t0 - 1)) / sr_, st, d1, d2, line);
            logChunk += lg;
            {
                const int stn = type == 0x80 ? (0x90 | ch) : st;
                const int bit = ((stn & 0x7F) << 7 | (type == 0xE0 || type == 0xD0 ? 0 : d1)) & 32767;
                ctrlSeen_[bit >> 5].fetch_or(1u << (bit & 31), std::memory_order_relaxed);
            }
            // statistics for the learner
            skr::KeyStat& k = statOf(type == 0xE0 ? (st << 8) : ((st << 8) | d1));
            if (k.count == 0) { if (mon_.keyFirst == 0) mon_.keyFirst = r.clock; }
            mon_.keyLast = r.clock;
            ++k.count;
            const int v = type == 0xE0 ? d2 : d2;
            if (k.last >= 0 && k.last != (type == 0xE0 ? d2 * 128 + d1 : d2)) ++k.changes;
            k.hist[v]++;
            k.rel64 += d2 - 64;
            k.rel2c += d2 < 64 ? d2 : d2 - 128;
            if (type == 0xE0)
            {
                const int full = d2 * 128 + d1;
                if (k.pb >= 0) { int d = full - k.pb; if (d > 8192) d -= 16384; else if (d < -8192) d += 16384; k.pbWrap += d; }
                k.pb = full; k.last = full;
            }
            else
            {
                if (k.last >= 0) { int d = d2 - k.last; if (d > 64) d -= 128; else if (d < -64) d += 128; k.absWrap += d; }
                k.last = d2;
                if (type == 0xB0 && d1 >= 32 && d1 < 64)
                {
                    const int full = mon_.lastMsb[(size_t)(ch * 32 + d1 - 32)] * 128 + d2;
                    int& lf = mon_.lastFull[(size_t)(ch * 32 + d1 - 32)];
                    // a 14-bit pair: replace the 7-bit wrap of the LSB by the full 14-bit movement
                    if (lf >= 0) { int d = full - lf; if (d > 8192) d -= 16384; else if (d < -8192) d += 16384; k.pbWrap += d; }   // 14-bit movement
                    lf = full;
                }
                if (type == 0xB0 && d1 < 32) mon_.lastMsb[(size_t)(ch * 32 + d1)] = d2;
            }
        }
        if (!logChunk.empty()) logAppend(logChunk);
        if (++mon_.secTick >= 66) { mon_.perSec = mon_.secCount; mon_.secCount = 0; mon_.secTick = 0; }
        if (tick % 7 == 0)
        {
            if (mon_.linesDirty)
            {
                { std::lock_guard<std::mutex> lk(textMutex_); for (int i = 0; i < 8; ++i) midiLines_[i] = mon_.lines[i]; }
                for (int i = 0; i < 8; ++i) bump(kMidiL1 + i);
                mon_.linesDirty = false;
            }
            std::string stat = "MSG " + std::to_string(mon_.total) + "  " + std::to_string(mon_.perSec) + "/S";
            if (midiRing_.dropped() > 0) stat += "  VOLL " + std::to_string(midiRing_.dropped());
            std::string t3;
            if (mon_.on)
            {
                const float secs = skr::kTestSteps[mon_.step].seconds;
                const float el = (float)mon_.ticksInStep * 0.015f;
                if (mon_.step == skr::kNumTestSteps - 1) t3 = "TEST BEENDEN: TEST STARTEN AUS";
                else if (secs > 0.0f && el < secs) t3 = fmt("NOCH %.0f S, DANN WEITER", (double)(secs - el));
                else t3 = "JETZT  WEITER  TIPPEN";
            }
            else t3 = "";
            bool chg;
            { std::lock_guard<std::mutex> lk(textMutex_); chg = midiStat_ != stat || midiTxt_[2] != t3; midiStat_ = stat; midiTxt_[2] = t3; }
            if (chg) { bump(kMidiStat); bump(kMidiT3); }
        }
        // live speed of the real platter (when it is followed)
        if (tick % 20 == 0)
        {
            const auto now = std::chrono::steady_clock::now();
            const double dt = std::chrono::duration<double>(now - mon_.lastSpeedT).count();
            const double t = platTurns_.load();
            std::string sp;
            {
                const std::string want = getInt(kCtrlProfile) == 1 ? std::string("SC6000M-PROFIL: 3600 SCHRITTE/U") : std::string();
                if (!want.empty())
                {
                    bool c2;
                    { std::lock_guard<std::mutex> lk(textMutex_); c2 = platInfo_ != want; if (c2) platInfo_ = want; }
                    if (c2) bump(kPlatInfo);
                }
            }
            if (platFollowOn_) sp = fmt("TELLER %.1f U/MIN", (t - mon_.lastTurns) / std::max(0.01, dt) * 60.0);
            else if (getBool(kPlatFollow)) sp = "ERST DEN TEST MACHEN";
            mon_.lastTurns = t; mon_.lastSpeedT = now;
            bool chg;
            { std::lock_guard<std::mutex> lk(textMutex_); chg = platSpeed_ != sp; platSpeed_ = sp; }
            if (chg) bump(kPlatSpeed);
        }
    }

    // loader thread: the log file in  <plugin folder>/SKRATCHA MIDI LOG/
    void logService()
    {
        std::string chunk;
        bool open, close;
        { std::lock_guard<std::mutex> lk(logMutex_); chunk.swap(logPending_); open = logOpenWanted_; close = logCloseWanted_; logOpenWanted_ = false; logCloseWanted_ = false; }
        if (open)
        {
            if (logFp_ != nullptr) { std::fclose(logFp_); logFp_ = nullptr; }
            std::string shown = "NICHT GESPEICHERT (LAUFWERK?)";
#if !defined(_WIN32)
            const std::string pf = mpc::pluginFolder();
            if (!pf.empty())
            {
                const std::string dir = pf + "/SKRATCHA MIDI LOG";
                mkdir(dir.c_str(), 0775);
                char nm[64];
                const std::time_t now = std::time(nullptr);
                std::strftime(nm, sizeof(nm), "MIDI %Y-%m-%d %H%M%S.txt", std::localtime(&now));
                logFp_ = std::fopen((dir + "/" + nm).c_str(), "w");
                if (logFp_ != nullptr) shown = std::string("LOG: ") + nm;
            }
#endif
            logBytes_ = 0;
            setText(midiFile_, shown, kMidiFile);
        }
        if (logFp_ != nullptr && !chunk.empty() && logBytes_ < (60u << 20))
        {
            std::fwrite(chunk.data(), 1, chunk.size(), logFp_);
            logBytes_ += chunk.size();
            std::fflush(logFp_);
        }
        if (close && logFp_ != nullptr)
        {
#if !defined(_WIN32)
            fsync(fileno(logFp_));
#endif
            std::fclose(logFp_); logFp_ = nullptr;
            setText(midiFile_, midiFile_ + " OK", kMidiFile);
        }
    }

    // ---- reporter helpers (2.4) ----
    void setText(std::string& dst, const std::string& v, int idx)
    {
        bool changed;
        { std::lock_guard<std::mutex> lk(textMutex_); changed = dst != v; if (changed) dst = v; }
        if (changed) bump(idx);
    }

    void liveReporter(int tick, float& lastRecTap, int& lastGrabSeen, int& lastLiveLed, int& lastRecLed, int& lastMeter, int& feedStale)
    {
        auto notify = [this](int idx) { if (effect_ != nullptr && host_ != nullptr) notifyHostParameterChanged(idx); };
        // retire old mappings 300 ms after they were swapped out (the audio thread has let go by then)
        for (int i = 0; i < 4; ++i)
            if (feedRetired_[i] != nullptr && tick >= feedRetireTick_[i]) { skrfeed::unmapChannel(feedRetired_[i]); feedRetired_[i] = nullptr; }
        auto swapFeed = [&](skrfeed::Shared* fresh)
        {
            skrfeed::Shared* old = feed_.exchange(fresh, std::memory_order_acq_rel);
            if (old == nullptr) return;
            for (int i = 0; i < 4; ++i)
                if (feedRetired_[i] == nullptr) { feedRetired_[i] = old; feedRetireTick_[i] = tick + 20; return; }
            feedRetired_[0] = old; feedRetireTick_[0] = tick + 20;   // never happens in practice
        };
        const int want = mpc::clamp(getInt(kFeedSrc), 0, skrfeed::kChannels - 1);
        skrfeed::Shared* f = feed_.load();
        if (want != feedCh_) { feedCh_ = want; swapFeed(skrfeed::mapChannel(want, false)); f = feed_.load(); feedStale = 0; }
        else if (f == nullptr && tick % 20 == 0) { swapFeed(skrfeed::mapChannel(want, false)); f = feed_.load(); }
        // a FEED that stopped for 1.5 s may have been removed and put back (new shared memory): map again
        static uint32_t lastAlive = 0;
        if (f != nullptr)
        {
            const uint32_t a = f->h.feedAlive.load();
            if (a != lastAlive) { lastAlive = a; feedStale = 0; } else ++feedStale;
            if (feedStale == 100) { swapFeed(skrfeed::mapChannel(want, false)); f = feed_.load(); }
        }
        const bool feedOk = f != nullptr && feedStale < 40;
        const double fsr = (f != nullptr && f->h.sampleRate.load() > 1000) ? (double)f->h.sampleRate.load() : sr_;
        if (tick % 10 == 0)
        {
            std::string info = "FEED " + std::to_string(want + 1) + ": ";
            if (f == nullptr) info += "NICHT GEFUNDEN";
            else if (!feedOk) info += "PAUSE / KEIN TON";
            else info += fmt("OK  %.0f KHZ", fsr / 1000.0) + (f->h.replaceMode.load() ? "  ERSETZT" : "  TROCKEN");
            setText(feedInfo_, info, kFeedInfo);
        }
        if (tick % 3 == 0)
        {
            const float pk = f != nullptr ? (float)f->h.peak.load() / 1000.0f : 0.0f;
            const int m = feedOk ? mpc::clamp((int)std::lround((20.0f * std::log10(std::max(1e-5f, pk)) + 48.0f) / 48.0f * 15.0f), 0, 15) : 0;
            if (m != lastMeter) { lastMeter = m; setNormalised(kFeedMeter, (float)m / 15.0f); notify(kFeedMeter); }
        }
        const int ll = liveLedOn_.load() ? 1 : 0;
        if (ll != lastLiveLed) { lastLiveLed = ll; set(kLiveLed, (float)ll); notify(kLiveLed); }
        if (getBool(kLiveOn) && !feedOk && tick % 20 == 0) setText(recInfo_, "LIVE: ERST SKRATCHA FEED SETZEN", kRecInfo);

        auto pushJob = [&](std::vector<float>&& data, double rate)
        {
            RecJob* j = new RecJob();
            j->data = std::move(data); j->sr = rate; j->deck = recDeck_; j->slot = recSlot_;
            std::lock_guard<std::mutex> lk(recJobMutex_);
            delete recJob_; recJob_ = j;
        };
        auto copyRange = [&](uint64_t from, uint64_t to, std::vector<float>& out)
        {
            for (uint64_t t = from; t < to; ++t)
            {
                const uint32_t k = (uint32_t)(t & skrfeed::kCapMask);
                out.push_back(f->cap[2 * k]); out.push_back(f->cap[2 * k + 1]);
            }
        };
        // REC: tap = start, tap again = stop (max 15 s); records into the current slot of the active deck
        if (getNormalised(kRecTap) != lastRecTap)
        {
            lastRecTap = getNormalised(kRecTap);
            if (!recOn_)
            {
                if (feedOk)
                {
                    recOn_ = true; recRead_ = f->h.writePos.load(std::memory_order_acquire);
                    recBuf_.clear(); recBuf_.reserve((size_t)(kMaxSeconds * fsr * 2.0) + 4096);
                    recDeck_ = mpc::clamp(getInt(kDeck), 0, 1); recSlot_ = mpc::clamp(getInt(deckP_[recDeck_].slot), 0, kSlots - 1);
                    setText(recInfo_, "AUFNAHME ...", kRecInfo);
                }
                else setText(recInfo_, "KEIN FEED: SKRATCHA FEED SETZEN", kRecInfo);
            }
            else
            {
                recOn_ = false;
                if (recBuf_.size() >= (size_t)(0.05 * fsr * 2.0)) { pushJob(std::move(recBuf_), fsr); setText(recInfo_, "SPEICHERE ...", kRecInfo); }
                else setText(recInfo_, "ZU KURZ", kRecInfo);
                recBuf_ = std::vector<float>();
            }
        }
        if (recOn_)
        {
            if (!feedOk) { recOn_ = false; setText(recInfo_, "FEED WEG: AUFNAHME ABGEBROCHEN", kRecInfo); }
            else
            {
                const uint64_t w = f->h.writePos.load(std::memory_order_acquire);
                if (w < recRead_ || w - recRead_ > skrfeed::kCapFrames / 2) recRead_ = w;
                const uint64_t maxFrames = (uint64_t)(kMaxSeconds * fsr);
                uint64_t to = w;
                if ((uint64_t)(recBuf_.size() / 2) + (to - recRead_) > maxFrames) to = recRead_ + (maxFrames - recBuf_.size() / 2);
                copyRange(recRead_, to, recBuf_); recRead_ = to;
                if (recBuf_.size() / 2 >= maxFrames)
                {
                    recOn_ = false; pushJob(std::move(recBuf_), fsr); recBuf_ = std::vector<float>();
                    setText(recInfo_, "15 S VOLL - SPEICHERE ...", kRecInfo);
                }
                else if (tick % 6 == 0) setText(recInfo_, fmt("AUFNAHME  %.1f S", (double)(recBuf_.size() / 2) / fsr), kRecInfo);
            }
        }
        const int rl = recOn_ ? 1 : 0;
        if (rl != lastRecLed) { lastRecLed = rl; set(kRecLed, (float)rl); notify(kRecLed); }
        // GRAB: the last 2 / 4 / 8 seconds, at once (the FEED ring always holds them)
        const int g = getInt(kGrabTap);
        if (g > 0 && g != lastGrabSeen)
        {
            static const double secs[4] = {0.0, 2.0, 4.0, 8.0};
            if (feedOk)
            {
                const uint64_t w = f->h.writePos.load(std::memory_order_acquire);
                const uint64_t n = std::min<uint64_t>(w, (uint64_t)(secs[g] * fsr));
                std::vector<float> data; data.reserve((size_t)n * 2);
                copyRange(w - n, w, data);
                recDeck_ = mpc::clamp(getInt(kDeck), 0, 1); recSlot_ = mpc::clamp(getInt(deckP_[recDeck_].slot), 0, kSlots - 1);
                if (n > 1000) { pushJob(std::move(data), fsr); setText(recInfo_, fmt("GRAB %.0f S - SPEICHERE ...", secs[g]), kRecInfo); }
            }
            else setText(recInfo_, "KEIN FEED: SKRATCHA FEED SETZEN", kRecInfo);
            set(kGrabTap, 0.0f); notify(kGrabTap);
        }
        lastGrabSeen = getInt(kGrabTap);
    }

    // smooth design change: dip the deck picture a little, switch the picture and its label at the darkest
    // point, fade back. Nothing is shown / hidden, so the MPC never redraws through another design.
    void designReporter(int* dip, int* shown, int (*lastLab)[kNumStyles], int* phase, bool labels, int layout)
    {
        auto notify = [this](int idx) { if (effect_ != nullptr && host_ != nullptr) notifyHostParameterChanged(idx); };
        const int shownP[3] = {kShownA, kShownB, kShownC}, dipP[3] = {kDipA, kDipB, kDipC}, labBase[3] = {kLabA, kLabB, kLabC};
        const int active = liveActive_.load();
        for (int k = 0; k < 3; ++k)
        {
            const int target = mpc::clamp(getInt(k == 2 ? kCStyle : deckP_[k].style), 0, kNumStyles - 1);
            if (shown[k] < 0) { shown[k] = target; set(shownP[k], (float)target); notify(shownP[k]); }
            bool switched = false;
            if (phase[k] == 0 && target != shown[k]) phase[k] = 1;                 // start the dip
            if (phase[k] == 1)
            {
                dip[k] = std::min(7, dip[k] + 4);
                if (dip[k] >= 7) { shown[k] = target; set(shownP[k], (float)target); notify(shownP[k]); phase[k] = 2; switched = true; }
            }
            else if (phase[k] == 2)
            {
                if (target != shown[k]) phase[k] = 1;
                else if (--dip[k] <= 0) { dip[k] = 0; phase[k] = 0; }
            }
            const float dv = (float)dip[k] / 7.0f;
            if (getNormalised(dipP[k]) != dv) { setNormalised(dipP[k], dv); notify(dipP[k]); }
            // labels: only the shown style's label turns (frames 1..48), the others show frame 0 (empty)
            if ((!labels && !switched) || layout == 2 || (k < 2 && layout != 1) || (k == 2 && layout != 0)) continue;
            const int d = k == 2 ? active : k;
            const double revs = liveRevs_[d].load();
            const int fr = 1 + mpc::clamp((int)((revs - std::floor(revs)) * kAngleFrames), 0, kAngleFrames - 1);
            for (int st = 0; st < kNumStyles; ++st)
            {
                const int v = st == shown[k] ? fr : 0;
                if (v != lastLab[k][st]) { lastLab[k][st] = v; setNormalised(labBase[k] + st, (float)v / (float)kAngleFrames); notify(labBase[k] + st); }
            }
        }
    }

    // a recording / grab: saved as a 24-bit WAV in My Samples/SKRATCHA REC, then loaded into its slot like any
    // file (so the project remembers it). If the drive is read-only it stays in memory only.
    void finishRecording(const RecJob& j)
    {
        const size_t frames = j.data.size() / 2;
        char stamp[32];
        const std::time_t now = std::time(nullptr);
        std::strftime(stamp, sizeof(stamp), "%H%M%S", std::localtime(&now));
        std::string name = std::string("REC ") + stamp;
        std::string path;
        const std::string pf = mpc::pluginFolder();
#if !defined(_WIN32)
        if (!pf.empty())
        {
            const std::string dir1 = pf + "/My Samples", dir2 = dir1 + "/SKRATCHA REC";
            mkdir(dir1.c_str(), 0775); mkdir(dir2.c_str(), 0775);
            std::string p = dir2 + "/" + name + ".wav";
            for (int n = 2; n < 100; ++n) { struct stat st; if (stat(p.c_str(), &st) != 0) break; p = dir2 + "/" + name + " " + std::to_string(n) + ".wav"; }
            if (writeWav24(p, j.data, frames, j.sr)) path = p;
        }
#endif
        const int d = j.deck, sl = j.slot;
        if (!path.empty())
        {
            { std::lock_guard<std::mutex> lk(wantMutex_); want_[d][sl] = path; }
            setText(recInfo_, "FERTIG: " + name + std::string(d ? " -> B" : " -> A") + std::to_string(sl + 1), kRecInfo);
            rescanRequested_.store(true);
        }
        else
        {
            // memory only
            Record* r = new Record();
            r->name = name; r->path = ""; r->sampleRate = j.sr; r->channels = 2; r->length = frames; r->len[0] = frames;
            for (int c = 0; c < 2; ++c) { r->lv[0][c].resize(frames); for (size_t i = 0; i < frames; ++i) r->lv[0][c][i] = j.data[2 * i + (size_t)c]; }
            buildMips(*r);
            for (int tries = 0; tries < 200 && (pending_[d][sl].load() != nullptr || retired_[d][sl].load() != nullptr); ++tries)
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            { std::lock_guard<std::mutex> lk(wantMutex_); want_[d][sl] = "MEM:" + name; }
            loaded_[d][sl] = "MEM:" + name;
            { std::lock_guard<std::mutex> lk(textMutex_); slotName_[d][sl] = name; }
            delete pending_[d][sl].exchange(r);
            setText(recInfo_, "NUR IM SPEICHER: " + name, kRecInfo);
        }
        bump(deckP_[d].names + sl); bump(deckP_[d].name); bump(kANames + sl); bump(kCName);
    }

    static bool writeWav24(const std::string& path, const std::vector<float>& inter, size_t frames, double rate)
    {
        FILE* fp = std::fopen(path.c_str(), "wb");
        if (fp == nullptr) return false;
        const size_t fade = std::min(frames / 4, (size_t)(0.002 * rate));
        const uint32_t dataBytes = (uint32_t)(frames * 2 * 3), sr = (uint32_t)std::lround(rate);
        auto u32 = [&](uint32_t v) { const uint8_t b[4] = {(uint8_t)v, (uint8_t)(v >> 8), (uint8_t)(v >> 16), (uint8_t)(v >> 24)}; std::fwrite(b, 1, 4, fp); };
        auto u16 = [&](uint16_t v) { const uint8_t b[2] = {(uint8_t)v, (uint8_t)(v >> 8)}; std::fwrite(b, 1, 2, fp); };
        std::fwrite("RIFF", 1, 4, fp); u32(36 + dataBytes); std::fwrite("WAVEfmt ", 1, 8, fp);
        u32(16); u16(1); u16(2); u32(sr); u32(sr * 6); u16(6); u16(24);
        std::fwrite("data", 1, 4, fp); u32(dataBytes);
        std::vector<uint8_t> buf; buf.reserve(6 * 4096);
        for (size_t i = 0; i < frames; ++i)
        {
            float g = 1.0f;
            if (i < fade) g = (float)i / (float)fade; else if (i + fade >= frames) g = (float)(frames - 1 - i) / (float)fade;
            for (int c = 0; c < 2; ++c)
            {
                float v = inter[2 * i + (size_t)c] * g;
                v = std::isfinite(v) ? mpc::clamp(v, -1.0f, 1.0f) : 0.0f;
                const int32_t q = (int32_t)std::lround(v * 8388607.0f);
                buf.push_back((uint8_t)q); buf.push_back((uint8_t)(q >> 8)); buf.push_back((uint8_t)(q >> 16));
            }
            if (buf.size() >= 6 * 4096) { std::fwrite(buf.data(), 1, buf.size(), fp); buf.clear(); }
        }
        if (!buf.empty()) std::fwrite(buf.data(), 1, buf.size(), fp);
        const bool ok = std::ferror(fp) == 0;
        return std::fclose(fp) == 0 && ok;
    }

    // ---- thread 3: the reporter. Cheap work only, every 15 ms: browser keys, texts, live values to the MPC ----
    void keepVisible(int sel, int count, std::atomic<int>& top)
    {
        int t = top.load();
        if (sel < t) t = sel;
        if (sel > t + 6) t = sel - 6;
        t = std::max(0, std::min(t, std::max(0, count - 7)));
        top.store(t);
    }

    void reporterLoop()
    {
        int tick = 0;
        float lastAngle[3] = {-1.0f, -1.0f, -1.0f}, lastStrobe[3] = {-1.0f, -1.0f, -1.0f};
        int lastStrip = -1, lastCut[2] = {-1, -1}, lastActive = -1, lastSlot[2] = {-1, -1}, lastCCut = -1;
        int lastGhost = -1, lastBeat = -1, lastStars = -1, lastMsg = -1, lastScore = -1, lastFade = -1, lastLesson = -1;
        int lastFolder = -1, lastFile = -1, lastDTop = -1, lastFTop = -1, lastLane = -1, lastPhase = -1, lastHit = -1;
        int lastPadCut = -1, lastPadHold = -1, lastPadCue = -1;
        int lastHint = -1, lastSync = -1, lastTour = -1, lastDesign = -1, lastLayout = -1, lastRun = -1;
        int lastNF = -1, lastFilesVer = -1, lastPadCutA = -1, lastPadCutB = -1;
        float lastDPos = -1.0f, lastFPos = -1.0f;
        float lastDTap[7], lastFTap[7];
        for (int r = 0; r < 7; ++r) { lastDTap[r] = getNormalised(kDTap + r); lastFTap[r] = getNormalised(kFTap + r); }
        float lastDScroll = getNormalised(kFolderScroll), lastFScroll = getNormalised(kFileScroll), accD = 0.0f, accF = 0.0f;
        int idleD = 0, idleF = 0;
        int lastDirsVer = -1, lastSub = -1;
        float lastRecTap = getNormalised(kRecTap);
        int lastGrabSeen = 0, lastLiveLed = -1, lastRecLed = -1, lastMeter = -1, feedStale = 0;
        int dip[3] = {0, 0, 0}, shown[3] = {-1, -1, -1}, lastLab[3][kNumStyles], dipPhase[3] = {0, 0, 0};
        for (auto& row : lastLab) for (int& v : row) v = -2;
        float lastOpenTap = getNormalised(kFolderOpenTap), lastBackTap = getNormalised(kFolderBackTap), lastLoadTap = getNormalised(kFileLoadTap);
        const auto t0 = std::chrono::steady_clock::now();
        auto notify = [this](int idx) { if (effect_ != nullptr && host_ != nullptr) notifyHostParameterChanged(idx); };
        while (!stopThread_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(15));
            ++tick;
            if (rescanDone_.exchange(false) && getBool(kRescan)) { set(kRescan, 0.0f); notify(kRescan); }

            // ---- browser: tap a row, double tap / OPEN to go in, step keys, sliders, Q-Links ----
            const int nF = numFolders_.load();
            const int dp = getInt(kFolderPick), fp = getInt(kFilePick), ds = getInt(kFolderStep), fs = getInt(kFileStep);
            if (dp > 0) { set(kBrFolder, (float)std::min(std::max(1, nF), folderTop_.load() + dp)); notify(kBrFolder); set(kFolderPick, 0.0f); notify(kFolderPick); }
            if (ds > 0)
            {
                const int step = ds == 1 ? -1 : ds == 2 ? 1 : ds == 3 ? -7 : 7;
                set(kBrFolder, (float)mpc::clamp(getInt(kBrFolder) + step, 1, std::max(1, nF))); notify(kBrFolder);
                set(kFolderStep, 0.0f); notify(kFolderStep);
            }
            // 2.4: a folder row (double tap or its arrow) OPENS that folder; a file row (double tap or its arrow)
            // LOADS that file into the current slot of the active deck. Swiping on the list scrolls it.
            bool openNow = false;
            for (int r = 0; r < 7; ++r)
            {
                if (getNormalised(kDTap + r) != lastDTap[r])
                {
                    lastDTap[r] = getNormalised(kDTap + r);
                    const int idx = folderTop_.load() + r;
                    if (idx < nF) { set(kBrFolder, (float)(idx + 1)); notify(kBrFolder); openNow = true; }
                }
                if (getNormalised(kFTap + r) != lastFTap[r])
                {
                    lastFTap[r] = getNormalised(kFTap + r);
                    const int idx = fileTop_.load() + r;
                    if (idx < numFiles_.load())
                    {
                        set(kBrFile, (float)(idx + 1)); notify(kBrFile);
                        const int d = mpc::clamp(getInt(kDeck), 0, 1);
                        loadRequest_.store(1 + mpc::clamp(getInt(deckP_[d].slot), 0, kSlots - 1));
                    }
                }
            }
            static const float kSwipeRows[3] = {8.0f, 16.0f, 32.0f};
            const float swipeRows = kSwipeRows[mpc::clamp(getInt(kSwipeSpeed), 0, 2)];
            auto swipe = [&](int param, float& lastV, float& acc, int& idle, std::atomic<int>& top, int count, int* bumpBase)
            {
                const float v = getNormalised(param);
                if (std::fabs(v - lastV) > 1e-5f)
                {
                    acc += (v - lastV) * swipeRows;      // the whole knob travel = 8 / 16 / 32 rows
                    lastV = v; idle = 0;
                    const int steps = (int)acc;
                    if (steps != 0)
                    {
                        acc -= (float)steps;
                        const int t = mpc::clamp(top.load() + steps, 0, std::max(0, count - 7));
                        top.store(t);
                        for (int r = 0; r < 7; ++r) bump(bumpBase[0] + r);
                    }
                }
                else if (++idle == 20 && std::fabs(v - 0.5f) > 1e-3f) { setNormalised(param, 0.5f); lastV = 0.5f; acc = 0.0f; notify(param); }
            };
            {
                int bd[1] = {kDRows}, bf[1] = {kFRows};
                swipe(kFolderScroll, lastDScroll, accD, idleD, folderTop_, nF, bd);
                swipe(kFileScroll, lastFScroll, accF, idleF, fileTop_, numFiles_.load(), bf);
            }
            // folder slider (swipe through the list)
            if (std::fabs(getNormalised(kFolderPos) - lastDPos) > 1e-4f && nF > 0)
            {
                lastDPos = getNormalised(kFolderPos);
                set(kBrFolder, (float)(1 + (int)std::lround((1.0f - lastDPos) * (nF - 1)))); notify(kBrFolder);   // slider top = first entry
            }
            // open (double tap / OPEN) or back
            const bool openTap = getNormalised(kFolderOpenTap) != lastOpenTap || openNow, backTap = getNormalised(kFolderBackTap) != lastBackTap;
            if (openTap || backTap)
            {
                lastOpenTap = getNormalised(kFolderOpenTap); lastBackTap = getNormalised(kFolderBackTap);
                std::lock_guard<std::mutex> lk(textMutex_);
                const int f = getInt(kBrFolder) - 1;
                std::string next = cwd_;
                const bool up = backTap || (f >= 0 && f < (int)dirs_.size() && dirs_[(size_t)f].kind == 0);
                if (up)
                {
                    if (!cwd_.empty())
                    {
                        if (isRootPath(cwd_) || cwd_ == "/") next.clear();
                        else { const size_t sl = cwd_.find_last_of('/'); next = sl == 0 ? std::string("/") : cwd_.substr(0, sl); }
                    }
                }
                else if (f >= 0 && f < (int)dirs_.size()) next = dirs_[(size_t)f].path;
                if (next != cwd_)
                {
                    cwd_ = next;
                    listReq_.store(true);
                    set(kBrFolder, 1.0f); notify(kBrFolder);
                    folderTop_.store(0); lastFolder = -1;
                }
            }
            int folder = getInt(kBrFolder);
            if (folder != lastFolder)
            {
                const bool sameEntry = lastFolder == folder;
                if (lastFolder >= 0 && !sameEntry) { set(kBrFile, 1.0f); notify(kBrFile); fileTop_.store(0); }
                lastFolder = folder; lastFile = -1;
                keepVisible(folder - 1, nF, folderTop_);
                {
                    std::lock_guard<std::mutex> lk(textMutex_);
                    const int f = folder - 1;
                    const std::string want = (f >= 0 && f < (int)dirs_.size()) ? dirs_[(size_t)f].path : std::string();
                    if (want != filesWant_ || getBool(kSubFolders) != filesDeep_) { filesWant_ = want; filesReq_.store(true); }
                }
                if (nF > 1) { lastDPos = 1.0f - (float)(folder - 1) / (float)(nF - 1); setNormalised(kFolderPos, lastDPos); notify(kFolderPos); }
                for (int r = 0; r < 7; ++r) bump(kDRows + r);
                bump(kBrFolderName); bump(kBrInfo);
            }
            if (nF != lastNF) { lastNF = nF; lastFolder = -1; }
            const int dv = dirsVersion_.load(), sub = getBool(kSubFolders) ? 1 : 0;
            if (dv != lastDirsVer || sub != lastSub) { lastDirsVer = dv; lastSub = sub; lastFolder = -1; }
            const int nFiles = numFiles_.load();
            if (filesVersion_.load() != lastFilesVer) { lastFilesVer = filesVersion_.load(); lastFile = -1; }
            if (fp > 0)
            {
                const int sel = std::min(std::max(1, nFiles), fileTop_.load() + fp);
                set(kBrFile, (float)sel); notify(kBrFile);
                set(kFilePick, 0.0f); notify(kFilePick);
                if (getBool(kAutoPreview) && !getBool(kBrPreview)) { set(kBrPreview, 1.0f); notify(kBrPreview); }
            }
            if (fs > 0)
            {
                const int step = fs == 1 ? -1 : fs == 2 ? 1 : fs == 3 ? -7 : 7;
                set(kBrFile, (float)mpc::clamp(getInt(kBrFile) + step, 1, std::max(1, nFiles))); notify(kBrFile);
                set(kFileStep, 0.0f); notify(kFileStep);
            }
            if (std::fabs(getNormalised(kFilePos) - lastFPos) > 1e-4f && nFiles > 0)
            {
                lastFPos = getNormalised(kFilePos);
                set(kBrFile, (float)(1 + (int)std::lround((1.0f - lastFPos) * (nFiles - 1)))); notify(kBrFile);
            }
            if (getInt(kBrFile) != lastFile)
            {
                lastFile = getInt(kBrFile);
                keepVisible(lastFile - 1, nFiles, fileTop_);
                if (nFiles > 1) { lastFPos = 1.0f - (float)(lastFile - 1) / (float)(nFiles - 1); setNormalised(kFilePos, lastFPos); notify(kFilePos); }
                for (int r = 0; r < 7; ++r) bump(kFRows + r);
                bump(kBrInfo);
            }
            // double tap on a file / LADEN: into the current slot of the active deck, onto the platter
            if (getNormalised(kFileLoadTap) != lastLoadTap)
            {
                lastLoadTap = getNormalised(kFileLoadTap);
                const int d = mpc::clamp(getInt(kDeck), 0, 1);
                loadRequest_.store(1 + mpc::clamp(getInt(deckP_[d].slot), 0, kSlots - 1));
            }
            if (folderTop_.load() != lastDTop) { lastDTop = folderTop_.load(); for (int r = 0; r < 7; ++r) bump(kDRows + r); }
            if (fileTop_.load() != lastFTop) { lastFTop = fileTop_.load(); for (int r = 0; r < 7; ++r) bump(kFRows + r); }
            {
                // highlight bars: which visible row holds the selection (0 = none visible)
                const int dsr = getInt(kBrFolder) - 1 - folderTop_.load(), fsr = getInt(kBrFile) - 1 - fileTop_.load();
                const int dv = (dsr >= 0 && dsr < 7 && nF > 0) ? dsr + 1 : 0, fv = (fsr >= 0 && fsr < 7 && nFiles > 0) ? fsr + 1 : 0;
                if (dv != getInt(kDSelRow)) { set(kDSelRow, (float)dv); notify(kDSelRow); }
                if (fv != getInt(kFSelRow)) { set(kFSelRow, (float)fv); notify(kFSelRow); }
            }

            // LOAD TO SLOT n: the selected file goes into slot n of the active deck and onto its platter
            const int lr = loadRequest_.exchange(0);
            if (lr > 0)
            {
                const std::string p = selectedPath();
                const int d = mpc::clamp(getInt(kDeck), 0, 1), sl = mpc::clamp(lr - 1, 0, kSlots - 1);
                if (!p.empty())
                {
                    { std::lock_guard<std::mutex> lk(wantMutex_); want_[d][sl] = p; }
                    std::lock_guard<std::mutex> lk(textMutex_);
                    slotName_[d][sl] = "LADE ...";
                }
                bump(kANames + sl); bump(kCName);
                set(deckP_[d].slot, (float)sl); notify(deckP_[d].slot);
                set(kBrLoad, 0.0f); notify(kBrLoad);
            }
            if (previewDone_.exchange(false) && getBool(kBrPreview)) { set(kBrPreview, 0.0f); notify(kBrPreview); }

            // ---- 2.4 LIVE: link to SKRATCHA FEED, REC / GRAB, status ----
            liveReporter(tick, lastRecTap, lastGrabSeen, lastLiveLed, lastRecLed, lastMeter, feedStale);
            midiReporter(tick);
            designReporter(dip, shown, lastLab, dipPhase, (tick & 1) == 0, getInt(kLayout));

            // a new lesson starts at its own tempo
            const int lesson = getInt(kHLesson);
            if (lesson != lastLesson)
            {
                if (lastLesson >= 0 && lesson > 0) { set(kHBpm, kLessons[mpc::clamp(lesson - 1, 0, kNumLessons - 1)].bpm); notify(kHBpm); }
                liveTour_.store(0);
                lastLesson = lesson;
                bump(kHText1); bump(kHText2); bump(kHScore);
            }

            if (effect_ == nullptr || host_ == nullptr) continue;

            // ---- live values, ~33 Hz ----
            if ((tick & 1) == 0)
            {
                const int active = liveActive_.load();
                const bool battle = getInt(kLayout) == 1;
                const bool turntable = getInt(kLayout) != 2;
                const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
                if (active != lastActive)
                {
                    lastActive = active;
                    for (int k = 0; k < 3; ++k) { lastAngle[k] = -1.0f; lastStrobe[k] = -1.0f; }
                    for (int sl = 0; sl < kSlots; ++sl) bump(kANames + sl);
                    bump(kCName);
                }
                // record angle and strobe: the active deck (k = 2) always, both decks in the BATTLE layout
                for (int k = 0; k < 3 && turntable; ++k)
                {
                    const int d = k == 2 ? active : k;
                    if (k < 2 && !battle) continue;
                    const int angP = k == 2 ? kCAngle : deckP_[d].angle, strP = k == 2 ? kCStrobe : deckP_[d].strobe;
                    const double revs = liveRevs_[d].load();
                    const float a = (float)(revs - std::floor(revs));
                    float da = std::fabs(a - lastAngle[k]); if (da > 0.5f) da = 1.0f - da;
                    if (lastAngle[k] < 0.0f || da >= 0.5f / kAngleFrames) { lastAngle[k] = a; setNormalised(angP, a); notifyHostParameterChanged(angP); }
                    const double ph = revs * kStrobeDots - secs * 100.0;
                    const float sp = (float)(ph - std::floor(ph));
                    float ds2 = std::fabs(sp - lastStrobe[k]); if (ds2 > 0.5f) ds2 = 1.0f - ds2;
                    if (lastStrobe[k] < 0.0f || ds2 >= 0.5f / kStrobeFrames) { lastStrobe[k] = sp; setNormalised(strP, sp); notifyHostParameterChanged(strP); }
                }
                for (int d = 0; d < 2; ++d)
                {
                    const int c = liveCut_[d].load() ? 1 : 0;
                    if (c != lastCut[d]) { lastCut[d] = c; set(deckP_[d].cutled, (float)c); notifyHostParameterChanged(deckP_[d].cutled); }
                    const int sl = liveSlot_[d].load();
                    if (sl != lastSlot[d]) { lastSlot[d] = sl; bump(deckP_[d].name); bump(kCName); }
                }
                auto report = [&](int idx, int v, int& last) { if (v != last) { last = v; set(idx, (float)v); notifyHostParameterChanged(idx); } };
                report(kCCutLed, liveCut_[active].load() ? 1 : 0, lastCCut);
                const int s = liveStrip_.load();
                if (s != lastStrip) { lastStrip = s; set(kStripLed, (float)s); notifyHostParameterChanged(kStripLed); }
                report(kHGhost, liveGhost_.load(), lastGhost);
                report(kHBeat, liveBeat_.load(), lastBeat);
                report(kHStars, liveStars_.load(), lastStars);
                report(kHFadeLed, liveFadeLed_.load() ? 1 : 0, lastFade);
                report(kHLane, liveLane_.load(), lastLane);
                report(kHHit, liveHit_.load(), lastHit);
                report(kPadCut, livePadCut_.load() ? 1 : 0, lastPadCut);
                report(kPadCutA, livePadCutA_.load() ? 1 : 0, lastPadCutA);
                report(kPadCutB, livePadCutB_.load() ? 1 : 0, lastPadCutB);
                report(kPadHold, livePadHold_.load() ? 1 : 0, lastPadHold);
                report(kPadCue, livePadCue_.load() ? 1 : 0, lastPadCue);
                const int ph = livePhase_.load();
                if (ph != lastPhase) { lastPhase = ph; bump(kHPhase); }
                report(kHint, liveHint_.load(), lastHint);
                report(kSync, liveSync_.load(), lastSync);
                const int tr = liveTour_.load();
                if (tr != lastTour) { lastTour = tr; bump(kHText1); bump(kHText2); bump(kHScore); bump(kHPhase); }
                const int dsg = getInt(deckP_[active].style) + 16 * active;
                if (dsg != lastDesign) { lastDesign = dsg; bump(kDesignName); }
                if (getInt(kLayout) != lastLayout) { lastLayout = getInt(kLayout); bump(kLayoutHint); }
                if (getBool(kHRun) != (lastRun == 1)) { lastRun = getBool(kHRun) ? 1 : 0; bump(kHText1); bump(kHText2); bump(kHPhase); }
                const int m = liveMsg_.load();
                if (m != lastMsg) { lastMsg = m; bump(kHMsg); }
                const int sc = liveScore_.load();
                if (sc != lastScore) { lastScore = sc; bump(kHScore); }
            }
            // parameter changes made by pads, and changed texts: every tick (fast feedback)
            for (int w = 0; w < kWords; ++w)
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
            if (needDisplayUpdate_.exchange(false)) requestDisplayUpdate();
        }
    }

    // ---------------------------------------------------------------------------------------------------------
    double sr_ = 44100.0;
    float agCoef_ = 0.0001f, agHpCoef_ = 0.07f, agSmooth_ = 0.0005f;   // auto gain: 250 ms power, 500 Hz split, 40 ms glide
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
    int releaseMode_ = 2;
    float lastScratch_ = 50.0f, lastJog_ = 0.0f;
    int mwMsb_ = 64, mwLsb_ = 0;
    // pads, cut
    int padBase_ = 36, cutDeck_ = 0, fireMode_ = 1;
    bool cutHeld_ = false, setCueHeld_ = false, readLater_ = false, cutOpenMode_ = false;
    bool slipOn_ = false, autoRun_ = true, cueHeld_ = false;
    int cueFlash_ = 0;
    float lastLayoutTap_ = 0.0f, lastCueTap_ = 0.0f, lastSetCueTap_ = 0.0f;
    bool tourActive_ = false, cutLatchOn_ = false;
    int tourMsg_ = 0;
    int cutLatchDeck_ = 0, layout_ = 0;
    int tourStep_ = 0, tourFlips_ = 0, tourSign_ = 0, tourSlot_ = 0;
    double tourMove_ = 0.0;
    float lastLookTap_ = 0.0f, lastCutLatch_ = 0.0f, lastHoldLatch_ = 0.0f;
    static constexpr int kNumMirrors = 12;
    int mirror_[kNumMirrors][3] = {};
    float mirrorP_[kNumMirrors] = {}, mirrorD_[kNumMirrors] = {};
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
    // ---- 2.5 MIDI monitor / platter ----
    skr::MidiRing midiRing_;
    skr::PlatterDecoder platDec_;
    bool midiMonOn_ = false, platFollowOn_ = false;
    float dcXl_ = 0.0f, dcYl_ = 0.0f, dcXr_ = 0.0f, dcYr_ = 0.0f;
    int platLast_[2] = {-1, -1}, platMsb_[2] = {0, 0}, scPitchMsb_[2] = {64, 64};
    double scSeenClock_ = -1.0e12;
    std::atomic<double> platTurns_{0.0};
    std::string midiTxt_[3], midiLines_[8], midiStat_, midiFile_ = "-", platInfo_ = "TELLER: NOCH NICHT ERKANNT", platSpeed_ = "";
    std::mutex logMutex_;
    std::string logPending_;
    bool logOpenWanted_ = false, logCloseWanted_ = false;
    FILE* logFp_ = nullptr;
    size_t logBytes_ = 0;
    // ---- 2.4 LIVE / RESAMPLE ----
    static constexpr uint32_t kLiveN = 1u << 19;       // live ring: 11.9 s at 44.1 kHz (power of two)
    std::atomic<skrfeed::Shared*> feed_{nullptr};      // mapped by the reporter, read by the audio thread
    skrfeed::Shared* feedRetired_[4] = {nullptr, nullptr, nullptr, nullptr};
    int feedRetireTick_[4] = {0, 0, 0, 0};
    int feedCh_ = -1;
    skrfeed::Shared* liveFeed_ = nullptr;              // audio thread's copy for this block
    Record* liveRec_ = nullptr;
    HalfbandFir fir_;
    uint64_t liveIn_ = 0, liveCnt_[kMipLevels] = {0, 0, 0, 0, 0, 0}, liveHeadU_ = 0;
    double liveHead_ = 0.0, liveLag_ = 608.0;
    int liveDeck_ = -1, maxBlock_ = 512, feedIdle_ = 100000000, feedLostBlocks_ = 0;
    uint32_t lastFeedAlive_ = 0;
    bool retOn_ = false;
    std::atomic<bool> liveLedOn_{false};
    // recording (reporter thread) and the job for the loader thread
    std::mutex recJobMutex_;
    RecJob* recJob_ = nullptr;
    std::vector<float> recBuf_;
    bool recOn_ = false;
    int recDeck_ = 0, recSlot_ = 0;
    uint64_t recRead_ = 0;
    std::string feedInfo_ = "FEED: -", recInfo_ = "REC: BEREIT";
    std::atomic<Record*> retired_[2][kSlots] = {};    // audio -> worker (deleted there)
    std::mutex wantMutex_;                           // never taken on the audio thread
    std::string want_[2][kSlots], loaded_[2][kSlots];
    std::string builtInDir_;
    std::mutex textMutex_;                           // names, browser index (never on the audio thread)
    std::string slotName_[2][kSlots];
    std::vector<DirEntry> dirs_;
    std::vector<std::string> files_, rootPaths_;
    std::string cwd_, filesDir_, filesWant_;
    std::atomic<int> dirsVersion_{0};
    std::atomic<bool> filesDeep_{true};
    bool filesSearching_ = false;
    std::atomic<bool> listing_{false}, listReq_{false}, filesReq_{false};
    std::atomic<int> numFiles_{0}, filesVersion_{0};
    std::atomic<int> loadRequest_{0};
    std::atomic<bool> rescanRequested_{false}, needDisplayUpdate_{false}, stopThread_{false};
    std::thread worker_, loader_, scanner_, motor_;
    std::atomic<uint32_t> platFrames_{0};

    // ---------------- SC6000M motor search ----------------
    // The host throws away plugin MIDI and holds the SC6000M's MIDI port itself. SKRATCHA runs inside the MPC
    // process, so it can write into that already open connection. Nothing is installed or changed; it only sends
    // notes / controllers, exactly what a DJ program sends to the SC6000M.
    static std::string readSmall(const std::string& path)
    {
        std::string out; FILE* f = std::fopen(path.c_str(), "r");
        if (f == nullptr) return out;
        char buf[4096]; size_t n = std::fread(buf, 1, sizeof(buf) - 1, f); std::fclose(f);
        out.assign(buf, n); return out;
    }
    int findScOut(std::string& report)
    {
        int found = -1;
        DIR* d = opendir("/proc/self/fd");
        if (d == nullptr) { report += "kein /proc/self/fd\n"; return -1; }
        while (dirent* e = readdir(d))
        {
            if (e->d_name[0] < '0' || e->d_name[0] > '9') continue;
            char link[256]; const std::string p = std::string("/proc/self/fd/") + e->d_name;
            const ssize_t n = readlink(p.c_str(), link, sizeof(link) - 1);
            if (n <= 0) continue;
            link[n] = 0;
            if (std::strncmp(link, "/dev/snd/", 9) != 0) continue;
            const std::string info = readSmall(std::string("/proc/self/fdinfo/") + e->d_name);
            unsigned flags = 0; const size_t fp = info.find("flags:");
            if (fp != std::string::npos) flags = (unsigned)std::strtoul(info.c_str() + fp + 6, nullptr, 8);
            int c = -1, dv = -1; std::string name;
            if (std::sscanf(link, "/dev/snd/midiC%dD%d", &c, &dv) == 2)
            {
                name = readSmall("/proc/asound/card" + std::to_string(c) + "/midi" + std::to_string(dv));
                name = name.substr(0, name.find('\n'));
            }
            char line[400]; std::snprintf(line, sizeof(line), "fd %s -> %s  flags %o  %s\n", e->d_name, link, flags, name.c_str());
            report += line;
            if (!name.empty() && name.find("SC6000") != std::string::npos && (flags & 3) != 0 && found < 0) found = std::atoi(e->d_name);
        }
        closedir(d);
        return found;
    }
    void motorLoop()
    {
        bool last = false;
        while (!stopThread_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            const bool on = getBool(kMotorScan);
            if (on && !last) runMotorScan();
            last = on;
        }
    }
    void runMotorScan()
    {
        std::string log;
        auto stamp = [] { char b[16]; std::time_t t = std::time(nullptr); std::strftime(b, sizeof(b), "%H:%M:%S ", std::localtime(&t)); return std::string(b); };
        auto save = [&] {
            if (FILE* f = std::fopen("/tmp/sc-motor.log", "w")) { std::fputs(log.c_str(), f); std::fclose(f); }
        };
        auto say = [&](const std::string& m) { log += stamp() + m + "\n"; save(); };
        auto show = [&](const std::string& m) { setText(platInfo_, m, kPlatInfo); };
        auto aborted = [&] { return stopThread_.load() || !getBool(kMotorScan); };
        auto sleepMs = [&](int ms) { for (int i = 0; i < ms / 50 && !aborted(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(50)); };

        say("SKRATCHA Motor-Suche (Plugin-Version)");
        log += readSmall("/proc/asound/cards");
        // the MPC reaches the SC6000M through the ALSA sequencer: SKRATCHA opens its own sequencer client
        skrseq::Client sq;
        const bool okSeq = sq.open("SC6000");
        log += sq.log; save();
        if (!okSeq) { say("FEHLER: SC6000M im Sequencer nicht gefunden"); show("MOTOR: SC6000M NICHT IM SEQUENCER"); return; }
        auto send = [&](int a, int b, int c) {
            const int t = a & 0xF0, ch = a & 15;
            if (t == 0x90) return sq.note(ch, b, c);
            if (t == 0x80) return sq.note(ch, b, 0);
            if (t == 0xB0) return sq.cc(ch, b, c);
            return false;
        };
        if (!send(0xB0, 123, 0)) { say(std::string("FEHLER: Senden geht nicht: ") + std::strerror(errno)); show("MOTOR: SENDEN GEHT NICHT"); return; }
        say("Senden geht.");
        auto rate = [&] {
            sq.drainPlatter();
            const uint32_t a = platFrames_.load(); int own = 0;
            for (int i = 0; i < 20 && !aborted(); ++i) { std::this_thread::sleep_for(std::chrono::milliseconds(50)); own += sq.drainPlatter(); }
            return std::max((int)(platFrames_.load() - a), own);
        };
        const int base = (rate() + rate()) / 2;
        const int th = std::max(200, base * 10 + 50);
        say("Ruhe: " + std::to_string(base) + " Teller-Frames/s, Schwelle " + std::to_string(th));
        int hits = 0;
        std::string hitList;
        auto probe = [&](int status, int num, const char* nm, int total) -> bool {
            char t[64]; std::snprintf(t, sizeof(t), "MOTOR SUCHT: %s %d/%d  TREFFER %d", nm, num, total, hits); show(t);
            send(status, num, 127);
            sleepMs(1000);
            const int r = rate();
            if ((status & 0xF0) == 0x90) send(0x80 | (status & 15), num, 0); else send(status, num, 0);
            if (aborted()) return false;
            char l[96];
            if (r > th)
            {
                ++hits; hitList += std::string(" ") + nm + " " + std::to_string(num);
                std::snprintf(l, sizeof(l), "TREFFER: %s %d -> Teller dreht (%d Frames/s)", nm, num, r); say(l);
                int i = 0; for (; i < 6 && !aborted(); ++i) if (rate() < th) break;
                if (i >= 6) { say("Teller dreht nach AUS weiter -> Suche stoppt hier."); return false; }
                say("  ... nach AUS wieder still.");
            }
            else { std::snprintf(l, sizeof(l), "%s %d: %d", nm, num, r); say(l); }
            return true;
        };
        bool ok = true;
        say("=== Noten Kanal 1 ===");
        for (int n = 0; n <= 127 && ok; ++n) ok = probe(0x90, n, "NOTE", 127);
        if (ok) say("=== CC Kanal 1 ===");
        for (int n = 0; n <= 119 && ok; ++n) ok = probe(0xB0, n, "CC", 119);
        say(std::string(aborted() ? "ABGEBROCHEN" : "FERTIG") + ". Treffer: " + std::to_string(hits) + hitList);
        show(hits ? "MOTOR TREFFER:" + hitList : std::string(aborted() ? "MOTOR-SUCHE ABGEBROCHEN" : "MOTOR: KEIN TREFFER"));
        const std::string pf = mpc::pluginFolder();
        if (!pf.empty()) { const std::string dir = pf + "/SKRATCHA MIDI LOG"; ::mkdir(dir.c_str(), 0755);
            if (FILE* f = std::fopen((dir + "/MOTOR-SUCHE.txt").c_str(), "w")) { std::fputs(log.c_str(), f); std::fclose(f); } }
    }
    static constexpr int kWords = (kNumParams + 63) / 64;
    std::atomic<int> folderTop_{0}, fileTop_{0}, numFolders_{0};
    std::atomic<bool> rescanDone_{false};
    std::atomic<bool> livePadCut_{false}, livePadHold_{false}, livePadCue_{false}, livePadCutA_{false}, livePadCutB_{false};
    std::atomic<int> liveLane_{0}, livePhase_{0}, liveHit_{0}, liveHint_{0}, liveTour_{0}, liveSync_{0};
    bool threadStarted_ = false;
    // live display values (audio -> background reporter)
    std::atomic<double> liveRevs_[2] = {};
    std::atomic<bool> liveCut_[2] = {};
    std::atomic<int> liveSlot_[2] = {}, liveStrip_{0}, liveActive_{0}, liveGhost_{0}, liveBeat_{0}, liveStars_{0}, liveMsg_{0}, liveScore_{0};
    std::atomic<int> liveBest_[kNumLessons] = {};
    std::atomic<bool> liveFadeLed_{false};
    std::atomic<uint64_t> dirty_[kWords] = {}, bumps_[kWords] = {};
};

MPC_PLUGIN_ENTRY(SKRATCHA)
