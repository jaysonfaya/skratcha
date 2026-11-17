// scratch_test.cpp - drives SKRATCHA like the MPC would, with simulated touch-strip (pitch bend) gestures,
// renders WAVs and writes a CSV of the MIDI it sent so the result can be analysed.
//
//   scratch_test <plugin.so> <scenario> <out.wav> [smooth_ms] [realtime]
//
// scenarios: baby | fast | hold_release | tone_baby | tone_fast | demo | jog | live
#include "mpc_vst2_abi.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <string>
#include <thread>
#include <vector>

static int g_automate = 0, g_update = 0;
static std::vector<int> g_automatedIdx;
static double g_samplePos = 0;
static VstTimeInfo g_time;

static VstIntPtr host(AEffect*, VstInt32 op, VstInt32 index, VstIntPtr, void*, float)
{
    switch (op)
    {
        case audioMasterVersion: return 2400;
        case audioMasterAutomate: ++g_automate; g_automatedIdx.push_back(index); return 0;
        case audioMasterUpdateDisplay: ++g_update; return 1;
        case audioMasterGetTime:
            std::memset(&g_time, 0, sizeof(g_time));
            g_time.sampleRate = 44100; g_time.samplePos = g_samplePos; g_time.tempo = 92; g_time.flags = kVstTempoValid;
            return (VstIntPtr)&g_time;
        default: return 0;
    }
}

struct Ev { int frame; uint8_t b0, b1, b2; };

int main(int argc, char** argv)
{
    if (argc < 4) { std::fprintf(stderr, "usage\n"); return 1; }
    std::string scen = argv[2];
    bool probe = false;
    if (scen.rfind("probe_", 0) == 0) { probe = true; scen = scen.substr(6); }
    const double smoothMs = argc > 4 ? std::atof(argv[4]) : 3.0;
    const bool realtime = argc > 5 && std::atoi(argv[5]) != 0;
    void* lib = dlopen(argv[1], RTLD_NOW);
    if (!lib) { std::fprintf(stderr, "%s\n", dlerror()); return 1; }
    auto entry = (AEffect* (*)(audioMasterCallback))dlsym(lib, "VSTPluginMain");
    AEffect* fx = entry(host);
    const double sr = 44100; const int bs = 128;
    fx->dispatcher(fx, effOpen, 0, 0, nullptr, 0);
    fx->dispatcher(fx, effSetSampleRate, 0, 0, nullptr, (float)sr);
    fx->dispatcher(fx, effSetBlockSize, 0, bs, nullptr, 0);
    fx->dispatcher(fx, effMainsChanged, 0, 1, nullptr, 0);

    auto setp = [&](int i, float n) { fx->setParameter(fx, i, n); };
    // parameter indices (keep in sync with SKRATCHA.cpp)
    enum { kLevel = 0, kSample, kPlay, kSpeed, kPitch, kPitchRange, kStart, kBrake, kStripRange, kStripDir, kRelease,
           kSmooth, kCatch, kCurve, kFader, kReverse, kCrackle, kPadBase, kLoop, kScratch, kJog, kAngle,
           kASlot = 33, kFireMode = 93, kHLesson = 80, kHRun = 81, kHDemo = 82, kHBpm = 83 };
    auto logNorm = [](double v, double lo, double hi) { return (float)(std::log(v / lo) / std::log(hi / lo)); };
    setp(kSmooth, logNorm(smoothMs, 0.5, 20.0));
    setp(kLevel, (float)((0.0 + 40.0) / 46.0));

    int sampleIndex = 1;   // 1 AHH, 4 TONE, 5 BREAK
    double seconds = 4.0;
    if (scen.rfind("tone", 0) == 0) sampleIndex = 4;
    if (scen == "demo") { sampleIndex = 1; seconds = 10.0; }
    if (scen == "tone_extreme") { setp(kStripRange, 1.0f); }
    if (scen == "fast") seconds = 3.0;
    if (probe) sampleIndex = 8;   // SKRATCHA_TEST_SLOT8 = the probe record
    setp(kFireMode, 0.0f);                                   // pads only cue (the scenarios start the motor with pad 9)
    setp(kASlot, (float)(std::min(sampleIndex, 8) - 1) / 7.0f);
    setp(kLoop, 1.0f);
    if (scen == "lesson_demo") { setp(kHLesson, 0.0f); setp(kHDemo, 1.0f); seconds = 8.0; }
    const bool practice = scen.rfind("practice", 0) == 0;   // practice_good | practice_wrong | practice_none
    if (practice) { setp(kHLesson, scen.find("forward") != std::string::npos ? 2.0f / 5.0f : 0.0f); setp(kHRun, 1.0f); seconds = 3.0 + 12.0 + 0.5; }
    std::this_thread::sleep_for(std::chrono::milliseconds(200));   // let the background thread load the record

    const int total = (int)(seconds * sr);
    std::vector<Ev> evs;
    auto pb = [&](int frame, double v)   // v -1..1, quantised to 14 bit like the strip
    {
        int val = (int)std::lround(v * 8192.0);
        if (val > 8191) val = 8191; if (val < -8192) val = -8192;
        const int u = val + 8192;
        evs.push_back({frame, 0xE0, (uint8_t)(u & 127), (uint8_t)(u >> 7)});
    };
    auto note = [&](int frame, int n, bool on) { evs.push_back({frame, (uint8_t)(on ? 0x90 : 0x80), (uint8_t)n, (uint8_t)(on ? 100 : 0)}); };
    const int evStep = (int)(0.002 * sr);   // the strip reports about every 2 ms

    auto gesture = [&](double t0, double t1, double freq, double amp, double offset)
    {
        // a finger stroking back and forth on the strip, then lifting (value snaps to 0)
        for (double t = t0; t < t1; t += evStep / sr)
        {
            double v = offset + amp * std::sin(2.0 * M_PI * freq * (t - t0) - M_PI / 2.0) + amp;   // starts at offset
            pb((int)(t * sr), v);
        }
        pb((int)(t1 * sr), 0.0);
    };

    if (scen == "baby" || scen == "tone_baby") gesture(0.3, 3.3, 1.5, 0.35, -0.5);
    else if (scen == "fast" || scen == "tone_fast" || scen == "tone_extreme") gesture(0.2, 2.7, 6.0, 0.45, -0.6);
    else if (scen == "hold_release")
    {
        note(0, 44, true); note(100, 44, false);                 // motor on (pad 9)
        pb((int)(1.0 * sr), -0.3);                               // grab and hold still for 0.5 s
        for (double t = 1.0; t < 1.5; t += evStep / sr) pb((int)(t * sr), -0.3);
        // drag back a quarter of the strip, then release: the record is caught by the motor
        for (double t = 1.5; t < 1.8; t += evStep / sr) pb((int)(t * sr), -0.3 - 0.4 * (t - 1.5) / 0.3);
        pb((int)(1.8 * sr), 0.0);
    }
    else if (scen == "demo")
    {
        // break-style routine on the AHH: baby scratches, transformer cuts with pad 37, a chirp, then release on the motor
        gesture(0.2, 2.2, 1.0, 0.3, -0.4);
        gesture(2.4, 4.4, 2.0, 0.3, -0.4);
        for (int k = 0; k < 16; ++k) { note((int)((4.6 + k * 0.0625) * sr), 45, true); note((int)((4.6 + k * 0.0625 + 0.03) * sr), 45, false); }
        gesture(4.6, 5.6, 2.0, 0.35, -0.45);
        gesture(5.9, 7.4, 4.0, 0.25, -0.3);
        note((int)(7.6 * sr), 44, true); note((int)(7.6 * sr) + 200, 44, false);   // motor on
        gesture(8.4, 9.0, 1.5, 0.2, -0.2);
    }
    else if (practice)
    {
        // follow (or not) the baby-scratch ghost: 80 BPM, 1/8 = 0.375 s, after a one-bar count-in (3 s)
        const double st = 60.0 / 80.0 / 2.0;
        for (double t = 3.0; t < 15.0; t += evStep / sr)
        {
            const double u = (t - 3.0) / st;
            const int k = (int)u; const double f = u - k;
            double a = (k % 2 == 0) ? -0.7 : 0.7, b = -a;
            if (scen == "practice_wrong") { a = -a; b = -b; }
            double v = a + (b - a) * (0.5 - 0.5 * std::cos(M_PI * f));
            if (v == 0.0) v = 1e-4;
            if (scen != "practice_none") pb((int)(t * sr), v);
        }
        if (scen.find("forward") != std::string::npos)
            for (int k = 0; k < 32; k += 2)   // pad 10 held on the forward strokes (CUT MODE = OPEN from the lesson)
            {
                note((int)((3.0 + k * st + 0.01) * sr), 45, true);
                note((int)((3.0 + (k + 1) * st - (scen == "practice_forward_late" ? -0.2 : 0.01)) * sr), 45, false);
            }
    }
    else if (scen == "jog")
    {
        // on-screen platter: finger turns the platter a quarter turn forth and back in 1 s
        std::sort(evs.begin(), evs.end(), [](const Ev& a, const Ev& b) { return a.frame < b.frame; });
    }

    std::sort(evs.begin(), evs.end(), [](const Ev& a, const Ev& b) { return a.frame < b.frame; });

    if (probe)
    {
        // pre-roll: run the motor for ~1.5 s so the record sits in the middle of the material, then stop it
        std::vector<float> a(bs), b(bs); float* o[2] = {a.data(), b.data()};
        setp(kStart, 0.0f); setp(kBrake, 0.0f); setp(kPlay, 1.0f);
        for (int k = 0; k < (int)(1.5 * sr / bs); ++k) fx->processReplacing(fx, nullptr, o, bs);
        setp(kPlay, 0.0f);
        for (int k = 0; k < (int)(0.3 * sr / bs); ++k) fx->processReplacing(fx, nullptr, o, bs);
        setp(kStart, logNorm(700, 30, 3000)); setp(kBrake, logNorm(900, 30, 5000));
    }
    std::vector<float> L((size_t)total), R((size_t)total);
    std::vector<float> bl(bs), br(bs);
    float* outs[2] = {bl.data(), br.data()};
    size_t ei = 0;
    std::vector<VstMidiEvent> mev(512);
    std::vector<char> evbuf(sizeof(VstEvents) + 512 * sizeof(VstEvent*));
    auto t0 = std::chrono::steady_clock::now();
    for (int pos = 0; pos < total; pos += bs)
    {
        const int n = std::min(bs, total - pos);
        VstEvents* ve = reinterpret_cast<VstEvents*>(evbuf.data());
        ve->numEvents = 0;
        while (ei < evs.size() && evs[ei].frame < pos + n)
        {
            VstMidiEvent& m = mev[(size_t)ve->numEvents];
            std::memset(&m, 0, sizeof(m));
            m.type = kVstMidiType; m.byteSize = sizeof(m); m.deltaFrames = std::max(0, evs[ei].frame - pos);
            m.midiData[0] = (char)evs[ei].b0; m.midiData[1] = (char)evs[ei].b1; m.midiData[2] = (char)evs[ei].b2;
            ve->events[ve->numEvents++] = reinterpret_cast<VstEvent*>(&m);
            ++ei;
        }
        if (scen == "jog")
        {
            const double t = pos / sr;
            if (t > 0.5 && t < 1.5)
            {
                const double ang = 90.0 * std::sin(M_PI * (t - 0.5));    // degrees
                double a = std::fmod(ang + 360.0, 360.0);
                setp(kJog, (float)(a / 360.0));
            }
        }
        fx->dispatcher(fx, effProcessEvents, 0, 0, ve, 0);
        g_samplePos = pos;
        fx->processReplacing(fx, nullptr, outs, n);
        for (int i = 0; i < n; ++i) { L[(size_t)(pos + i)] = bl[(size_t)i]; R[(size_t)(pos + i)] = br[(size_t)i]; }
        if (realtime)
        {
            auto due = t0 + std::chrono::microseconds((long long)((pos + n) / sr * 1e6));
            std::this_thread::sleep_until(due);
        }
    }

    // write WAV (float32 stereo)
    FILE* f = std::fopen(argv[3], "wb");
    auto u32 = [&](uint32_t v) { std::fwrite(&v, 4, 1, f); };
    auto u16 = [&](uint16_t v) { std::fwrite(&v, 2, 1, f); };
    const uint32_t dataBytes = (uint32_t)total * 2 * 4;
    std::fwrite("RIFF", 1, 4, f); u32(36 + dataBytes); std::fwrite("WAVEfmt ", 1, 8, f);
    u32(16); u16(3); u16(2); u32(44100); u32(44100 * 8); u16(8); u16(32);
    std::fwrite("data", 1, 4, f); u32(dataBytes);
    for (int i = 0; i < total; ++i) { std::fwrite(&L[(size_t)i], 4, 1, f); std::fwrite(&R[(size_t)i], 4, 1, f); }
    std::fclose(f);

    // events CSV for analysis
    std::string csv = std::string(argv[3]) + ".events.csv";
    FILE* c = std::fopen(csv.c_str(), "w");
    for (const Ev& e : evs) std::fprintf(c, "%d,%d,%d,%d\n", e.frame, e.b0, e.b1, e.b2);
    std::fclose(c);

    for (int idx : {85, 86, 87, 88, 89, 91})
    {
        char txt[256] = {0};
        fx->dispatcher(fx, effGetParamDisplay, idx, 0, txt, 0);
        std::printf("param %d: %s\n", idx, txt);
    }
    int angleReports = 0; for (int i : g_automatedIdx) if (i == kAngle) ++angleReports;
    std::printf("automate=%d (angle %d) updateDisplay=%d\n", g_automate, angleReports, g_update);
    fx->dispatcher(fx, effMainsChanged, 0, 0, nullptr, 0);
    fx->dispatcher(fx, effClose, 0, 0, nullptr, 0);
    return 0;
}
