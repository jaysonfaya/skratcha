// live_test.cpp - SKRATCHA FEED + SKRATCHA in one process, like on the MPC: FEED is an insert on a
// track playing a 1 kHz tone (with a short click every 0.5 s), SKRATCHA scratches it LIVE, records it.
//
//   live_test <skratcha.so> <feed.so> <out_prefix> [order: 0 = SKRATCHA first, 1 = FEED first]
#include "mpc_vst2_abi.h"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <string>
#include <thread>
#include <vector>

static VstTimeInfo g_time;
static VstIntPtr host(AEffect*, VstInt32 op, VstInt32, VstIntPtr, void*, float)
{
    if (op == audioMasterVersion) return 2400;
    if (op == audioMasterGetTime) { std::memset(&g_time, 0, sizeof(g_time)); g_time.sampleRate = 44100; g_time.tempo = 92; g_time.flags = kVstTempoValid; return (VstIntPtr)&g_time; }
    return 0;
}

static AEffect* load(const char* path)
{
    void* lib = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!lib) { std::fprintf(stderr, "%s\n", dlerror()); std::exit(1); }
    auto entry = (AEffect* (*)(audioMasterCallback))dlsym(lib, "VSTPluginMain");
    AEffect* fx = entry(host);
    fx->dispatcher(fx, effOpen, 0, 0, nullptr, 0);
    fx->dispatcher(fx, effSetSampleRate, 0, 0, nullptr, 44100.0f);
    fx->dispatcher(fx, effSetBlockSize, 0, 128, nullptr, 0);
    fx->dispatcher(fx, effMainsChanged, 0, 1, nullptr, 0);
    return fx;
}

static int findParam(AEffect* fx, const char* name)
{
    for (int i = 0; i < fx->numParams; ++i)
    {
        char buf[256] = {0};
        fx->dispatcher(fx, effGetParamName, i, 0, buf, 0);
        if (std::strcmp(buf, name) == 0) return i;
    }
    std::fprintf(stderr, "param %s not found\n", name); std::exit(1);
}

static std::string display(AEffect* fx, int i)
{
    char buf[256] = {0};
    fx->dispatcher(fx, effGetParamDisplay, i, 0, buf, 0);
    return buf;
}

static void writeWav(const std::string& fn, const std::vector<float>& L, const std::vector<float>& R)
{
    FILE* f = std::fopen(fn.c_str(), "wb");
    const uint32_t n = (uint32_t)L.size(), bytes = n * 8;
    auto u32 = [&](uint32_t v) { std::fwrite(&v, 4, 1, f); };
    auto u16 = [&](uint16_t v) { std::fwrite(&v, 2, 1, f); };
    std::fwrite("RIFF", 1, 4, f); u32(36 + bytes); std::fwrite("WAVEfmt ", 1, 8, f); u32(16); u16(3); u16(2); u32(44100); u32(44100 * 8); u16(8); u16(32);
    std::fwrite("data", 1, 4, f); u32(bytes);
    for (uint32_t i = 0; i < n; ++i) { std::fwrite(&L[i], 4, 1, f); std::fwrite(&R[i], 4, 1, f); }
    std::fclose(f);
}

struct MidiBlock { VstInt32 numEvents; VstIntPtr reserved; VstEvent* events[8]; };

int main(int argc, char** argv)
{
    if (argc < 4) return 1;
    const int order = argc > 4 ? std::atoi(argv[4]) : 0;
    AEffect* sk = load(argv[1]);
    AEffect* fe = load(argv[2]);
    const int pLive = findParam(sk, "Live"), pRec = findParam(sk, "Rec Tap"), pGrab = findParam(sk, "Grab");
    const int pFeedInfo = findParam(sk, "Feed Info"), pRecInfo = findParam(sk, "Rec Info"), pFStatus = findParam(fe, "Status");
    const int bs = 128; const double sr = 44100.0, total = 7.0;
    std::vector<float> inL(bs), inR(bs), fo0(bs), fo1(bs), so0(bs), so1(bs);
    std::vector<float> FL, FR, SL, SR;
    double ph = 0.0;
    VstMidiEvent mev; MidiBlock mb;
    auto pb = [&](double v)
    {
        const int val = std::max(0, std::min(16383, (int)std::lround(8192 + v * 8191)));
        std::memset(&mev, 0, sizeof(mev)); mev.type = kVstMidiType; mev.byteSize = sizeof(mev);
        mev.midiData[0] = (char)0xE0; mev.midiData[1] = (char)(val & 127); mev.midiData[2] = (char)(val >> 7);
        mb.numEvents = 1; mb.reserved = 0; mb.events[0] = (VstEvent*)&mev;
        sk->dispatcher(sk, effProcessEvents, 0, 0, &mb, 0);
    };
    const auto t0 = std::chrono::steady_clock::now();
    for (int b = 0; b * bs < (int)(total * sr); ++b)
    {
        const double t = b * bs / sr;
        // the "track": 1 kHz tone, a click every 0.5 s
        for (int i = 0; i < bs; ++i)
        {
            const double tt = (b * bs + i) / sr;
            float v = 0.4f * (float)std::sin(ph); ph += 2.0 * M_PI * 1000.0 / sr;
            if (std::fmod(tt, 0.5) < 0.002) v += 0.5f;
            inL[(size_t)i] = inR[(size_t)i] = v;
        }
        auto at = [&](double when) { return t <= when && when < t + bs / sr; };
        if (at(1.0)) sk->setParameter(sk, pLive, 1.0f);
        if (t >= 2.0 && t < 2.4) pb(-0.6 * std::sin((t - 2.0) / 0.4 * M_PI));          // drag back and forth
        if (at(2.4)) pb(0.0);                                                             // let go
        if (at(3.5)) sk->setParameter(sk, pLive, 0.0f);
        if (at(4.0)) sk->setParameter(sk, pRec, 1.0f);
        if (at(5.0)) sk->setParameter(sk, pRec, 0.0f);
        if (at(5.5)) sk->setParameter(sk, pGrab, 1.0f / 3.0f);
        float* fin[2] = {inL.data(), inR.data()}; float* fout[2] = {fo0.data(), fo1.data()};
        float* sout[2] = {so0.data(), so1.data()};
        if (order == 0) { sk->processReplacing(sk, nullptr, sout, bs); fe->processReplacing(fe, fin, fout, bs); }
        else { fe->processReplacing(fe, fin, fout, bs); sk->processReplacing(sk, nullptr, sout, bs); }
        for (int i = 0; i < bs; ++i) { FL.push_back(fo0[(size_t)i]); FR.push_back(fo1[(size_t)i]); SL.push_back(so0[(size_t)i]); SR.push_back(so1[(size_t)i]); }
        if (b % 172 == 0) std::printf("%.1fs  feed: %-28s rec: %-30s FEED: %s\n", t, display(sk, pFeedInfo).c_str(), display(sk, pRecInfo).c_str(), display(fe, pFStatus).c_str());
        std::this_thread::sleep_until(t0 + std::chrono::microseconds((long long)((b + 1) * bs / sr * 1e6)));
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(800));
    std::printf("end   rec: %s\n", display(sk, pRecInfo).c_str());
    writeWav(std::string(argv[3]) + "_feed.wav", FL, FR);
    writeWav(std::string(argv[3]) + "_skr.wav", SL, SR);
    sk->dispatcher(sk, effClose, 0, 0, nullptr, 0);
    fe->dispatcher(fe, effClose, 0, 0, nullptr, 0);
    return 0;
}
