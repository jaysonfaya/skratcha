// emulates a motorised platter controller: heartbeat note + platter messages of a chosen kind
#include "mpc_vst2_abi.h"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <string>
#include <thread>
#include <vector>
static VstTimeInfo g_time;
static VstIntPtr host(AEffect*, VstInt32 op, VstInt32, VstIntPtr, void*, float)
{
    if (op == audioMasterVersion) return 2400;
    if (op == audioMasterGetTime) { memset(&g_time, 0, sizeof(g_time)); g_time.sampleRate = 44100; g_time.tempo = 92; g_time.flags = kVstTempoValid; return (VstIntPtr)&g_time; }
    return 0;
}
AEffect* fx; std::vector<float> a(128), b(128); float* o[2] = {a.data(), b.data()};
std::vector<float> OUT;
int find(const char* n) { for (int i = 0; i < fx->numParams; ++i) { char x[256] = {0}; fx->dispatcher(fx, effGetParamName, i, 0, x, 0); if (!strcmp(x, n)) return i; } printf("no %s\n", n); return -1; }
std::string disp(int i) { char x[256] = {0}; fx->dispatcher(fx, effGetParamDisplay, i, 0, x, 0); return x; }
struct Ev { VstMidiEvent e; };
bool hb = false; const char* kind; double cpr = 3600; double pos = 0; int lastAbs = 0; int blk = 0;
// one block: platter at rpm (turns/min); emits messages every ~1 ms (as fast as the block allows: 4 per block)
void block(double rpm, bool platter)
{
    std::vector<VstMidiEvent> evs; 
    auto add = [&](int off, int s, int d1, int d2) { VstMidiEvent e; memset(&e, 0, sizeof(e)); e.type = kVstMidiType; e.byteSize = sizeof(e); e.deltaFrames = off; e.midiData[0] = (char)s; e.midiData[1] = (char)d1; e.midiData[2] = (char)d2; evs.push_back(e); };
    if (hb && blk % 3 == 0) add(0, 0x90, 0x38, 0x7F);   // heartbeat
    if (platter)
        for (int k = 0; k < 4; ++k)
        {
            pos += rpm / 60.0 * 32.0 / 44100.0 * cpr;      // counts
            const int full = (int)std::floor(pos);
            int d = full - lastAbs; lastAbs = full;
            if (!strcmp(kind, "rel64")) { if (d) add(k * 32, 0xB0, 0x1F, 64 + std::max(-63, std::min(63, d))); }
            else if (!strcmp(kind, "rel2c")) { if (d) add(k * 32, 0xB0, 0x1F, d >= 0 ? d : 128 + d); }
            else if (!strcmp(kind, "cc14")) { const int v = ((full % 16384) + 16384) % 16384; add(k * 32, 0xB0, 0x06, v >> 7); add(k * 32, 0xB0, 0x26, v & 127); }
            else { const int v = ((full % 16384) + 16384) % 16384; add(k * 32, 0xE0, v & 127, v >> 7); }
        }
    struct { VstInt32 n; VstIntPtr r; VstEvent* e[64]; } list; list.n = (int)evs.size(); list.r = 0;
    for (size_t i = 0; i < evs.size(); ++i) list.e[i] = (VstEvent*)&evs[i];
    fx->dispatcher(fx, effProcessEvents, 0, 0, &list, 0);
    fx->processReplacing(fx, nullptr, o, 128);
    for (int i = 0; i < 128; ++i) OUT.push_back(a[i]);
    ++blk;
}
void run(double secs, double rpm, bool platter, std::chrono::steady_clock::time_point& t0) { int n = (int)(secs * 44100 / 128); for (int i = 0; i < n; ++i) { block(rpm, platter); std::this_thread::sleep_until(t0 + std::chrono::microseconds((long long)(blk * 128 / 44100.0 * 1e6))); } }
void flip(int p) { fx->setParameter(fx, p, fx->getParameter(fx, p) > 0.5f ? 0.f : 1.f); }
double freq(size_t from, size_t n) { // zero crossings
    int z = 0; for (size_t i = from + 1; i < from + n; ++i) if (OUT[i - 1] < 0 && OUT[i] >= 0) ++z; return z / (n / 44100.0); }
int main(int, char** argv)
{
    kind = argv[2];
    void* lib = dlopen(argv[1], RTLD_NOW);
    fx = ((AEffect* (*)(audioMasterCallback))dlsym(lib, "VSTPluginMain"))(host);
    fx->dispatcher(fx, effOpen, 0, 0, nullptr, 0); fx->dispatcher(fx, effSetSampleRate, 0, 0, nullptr, 44100.f);
    fx->dispatcher(fx, effSetBlockSize, 0, 128, nullptr, 0); fx->dispatcher(fx, effMainsChanged, 0, 1, nullptr, 0);
    fx->setParameter(fx, find("A Slot"), 1.0f); fx->setParameter(fx, find("Slot"), 1.0f);
    auto t0 = std::chrono::steady_clock::now();
    run(1.5, 0, false, t0);
    if (getenv("PLAYTEST")) { fx->setParameter(fx, find("A Start/Stop"), 1.0f); size_t s0 = OUT.size(); run(1.5, 0, false, t0); double e=0; for (size_t i=s0;i<OUT.size();++i) e+=OUT[i]*OUT[i]; printf("ss=%.2f max=%.4f ", fx->getParameter(fx, find("A Start/Stop")), [](){float m=0; for(float v:OUT) m=std::max(m,std::fabs(v)); return m;}()); printf("play rms %.4f freq %.1f name %s\n", std::sqrt(e/(OUT.size()-s0)), freq(s0+22050,22050), disp(find("Record")).c_str()); return 0; }
    fx->setParameter(fx, find("Midi Monitor"), 1.0f); hb = true;
    run(1.0, 0, false, t0);                 // step 1
    flip(find("Midi Next"));                // -> step 2
    run(3.0, 33.3333, true, t0);            // motor 3 s
    flip(find("Midi Next"));                // learn
    run(0.3, 0, false, t0);
    printf("[%s] info: %s\n", kind, disp(find("Platter Info")).c_str());
    fx->setParameter(fx, find("Midi Monitor"), 0.0f);
    fx->setParameter(fx, find("Platter Follow"), 1.0f);
    run(0.3, 0, false, t0);
    size_t s1 = OUT.size(); run(1.5, 33.3333, true, t0);
    printf("  speed: %s  freq at 33: %.1f Hz\n", disp(find("Platter Speed")).c_str(), freq(s1 + 22050, 22050));
    size_t s2 = OUT.size(); run(1.5, 45.0, true, t0);
    printf("  speed: %s  freq at 45: %.1f Hz\n", disp(find("Platter Speed")).c_str(), freq(s2 + 22050, 22050));
    size_t s3 = OUT.size(); run(1.0, -33.3333, true, t0);
    printf("  freq backwards: %.1f Hz  %.1f  %.1f  speed %s\n", freq(s3 + 22050, 11025), freq(s3+5000,11025), freq(s3+33075,11025), disp(find("Platter Speed")).c_str());
    size_t s4 = OUT.size(); run(2.0, 0, false, t0);
    for (int w = 0; w < 8; ++w) { double q=0; size_t f=s4+w*11025; for (size_t i=f;i<f+11025;++i) q+=OUT[i]*OUT[i]; printf(" w%d %.3f/%.0fHz", w, std::sqrt(q/11025), freq(f,11025)); } printf("\n");
    double e = 0; for (size_t i = s4 + 22050; i < OUT.size(); ++i) e += OUT[i] * OUT[i];
    printf("  platter stopped: rms %.4f  file: %s\n", std::sqrt(e / (OUT.size() - s4 - 22050)), disp(find("Midi File")).c_str());
    fx->dispatcher(fx, effClose, 0, 0, nullptr, 0);
}
