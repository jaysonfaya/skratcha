// skr_midimon.h - SKRATCHA: MIDI monitor, guided controller test (made for the Denon SC6000M) and the
// platter decoder that lets the deck follow a real motorised platter.
//
// Audio thread: pushes every MIDI event into a lock-free ring, and (when "Teller folgt" is on) decodes the
// learned platter message into turns. Reporter thread: drains the ring, keeps statistics per message,
// learns the platter. Loader thread: writes the log file. Nothing here sends MIDI (plugins cannot).
#pragma once

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace skr {

struct MidiRec { uint64_t clock; uint8_t b[3]; uint8_t n; };

class MidiRing
{
public:
    static constexpr uint32_t kSize = 1u << 14, kMask = kSize - 1;
    bool push(const MidiRec& r)
    {
        const uint32_t h = head_.load(std::memory_order_relaxed);
        if (h - tail_.load(std::memory_order_acquire) >= kSize) { dropped_.fetch_add(1, std::memory_order_relaxed); return false; }
        buf_[h & kMask] = r;
        head_.store(h + 1, std::memory_order_release);
        return true;
    }
    bool pop(MidiRec& r)
    {
        const uint32_t t = tail_.load(std::memory_order_relaxed);
        if (t == head_.load(std::memory_order_acquire)) return false;
        r = buf_[t & kMask];
        tail_.store(t + 1, std::memory_order_release);
        return true;
    }
    uint32_t dropped() const { return dropped_.load(); }
private:
    MidiRec buf_[kSize];
    std::atomic<uint32_t> head_{0}, tail_{0}, dropped_{0};
};

// the learned platter message, read by the audio thread
struct PlatterDecoder
{
    enum Kind { kNone = 0, kRel64, kRel2c, kAbs7, kAbs14Pb, kAbs14Cc };
    std::atomic<int> kind{kNone};
    std::atomic<int> status{0};          // 0xB0 / 0xE0 / 0x90 (type only)
    std::atomic<int> d1{0};              // controller / note number (CC MSB for kAbs14Cc)
    std::atomic<int> baseCh{0};          // channel of layer A; baseCh + 1 = layer B
    std::atomic<float> turnsPerCount{0.0f};   // signed: positive = forward
};

// one line of the guided test
struct TestStep { const char* l1; const char* l2; float seconds; };

static const TestStep kTestSteps[] = {
    {"TIPPE AUF  TEST STARTEN", "MONITOR + PROTOKOLL LAUFEN", 0.0f},
    {"1  SC6000M IM COMPUTER-MODUS", "NICHTS ANFASSEN, 5 S WARTEN", 5.0f},
    {"2  MOTOR-TASTE EIN (33 U/MIN)", "TELLER 10 S FREI LAUFEN LASSEN", 10.0f},
    {"3  TELLER MIT DER HAND STOPPEN", "UND 3 S FESTHALTEN, LOSLASSEN", 6.0f},
    {"4  LANGSAM VOR UND ZURUECK", "SCHIEBEN (ETWA 5 S)", 5.0f},
    {"5  SCHNELLE SCRATCHES", "ETWA 5 S", 5.0f},
    {"6  TELLER NUR ANTIPPEN", "UND LOSLASSEN (3x)", 5.0f},
    {"7  MOTOR AUS. TELLER VON HAND", "GENAU 1 UMDREHUNG VORWAERTS", 8.0f},
    {"8  PITCH-FADER GANZ HOCH,", "GANZ RUNTER, DANN IN DIE MITTE", 6.0f},
    {"9  PLAY 2x DRUECKEN,", "DANN CUE 2x DRUECKEN", 5.0f},
    {"10  PADS 1 BIS 8", "NACHEINANDER DRUECKEN", 6.0f},
    {"11  ALLE ANDEREN TASTEN UND", "KNOEPFE NACHEINANDER", 20.0f},
    {"12  LAYER WECHSELN, TELLER", "KURZ DREHEN, LAYER ZURUECK", 8.0f},
    {"FERTIG - PROTOKOLL GESPEICHERT", "TELLER FOLGT = JETZT TESTEN", 0.0f},
};
constexpr int kNumTestSteps = (int)(sizeof(kTestSteps) / sizeof(kTestSteps[0]));

inline const char* midiTypeName(uint8_t st)
{
    switch (st & 0xF0)
    {
        case 0x80: return "NOTE OFF"; case 0x90: return "NOTE ON"; case 0xA0: return "POLY AT";
        case 0xB0: return "CC"; case 0xC0: return "PROGRAM"; case 0xD0: return "CH AT"; case 0xE0: return "PITCHBEND";
        default: return "SYS";
    }
}

// statistics of one message key (type + channel + number) during a test step
struct KeyStat
{
    int key = 0;                  // (status << 8) | d1  (status includes the channel)
    int count = 0, changes = 0, last = -1;
    int hist[128] = {0};
    long long rel64 = 0, rel2c = 0, absWrap = 0;
    int pb = -1; long long pbWrap = 0;
};

} // namespace skr
