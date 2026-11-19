// SKRATCHA - minimal ALSA sequencer client (kernel interface, no libasound)
// The MPC talks to USB MIDI controllers through /dev/snd/seq. The sequencer accepts any number of clients, so
// SKRATCHA opens its own client and port and sends straight to the controller (the host throws plugin MIDI away).
// Nothing is installed or changed; the client disappears when the plugin closes.
#pragma once
#include <cstdint>
#include <cstring>
#include <string>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <cerrno>
#include <cstdio>

namespace skrseq
{
struct Addr { unsigned char client, port; };
struct NoteEv { unsigned char channel, note, velocity, off_velocity; unsigned int duration; };
struct CtrlEv { unsigned char channel, u1, u2, u3; unsigned int param; int value; };
union Data { NoteEv note; CtrlEv control; unsigned char raw[12]; unsigned int raw32[3]; };
struct Event
{
    unsigned char type, flags; char tag; unsigned char queue;
    unsigned int time[2];
    Addr source, dest;
    Data data;
};
static_assert(sizeof(Event) == 28, "snd_seq_event layout");
struct ClientInfo
{
    int client; int type; char name[64]; unsigned int filter; unsigned char multicast_filter[8];
    unsigned char event_filter[32]; int num_ports, event_lost, card, pid; char reserved[56];
};
struct PortInfo
{
    Addr addr; char name[64]; unsigned int capability, type; int midi_channels, midi_voices, synth_voices;
    int read_use, write_use; void* kernel; unsigned int flags; unsigned char time_queue; char reserved[59];
};
struct Subscribe { Addr sender, dest; unsigned int voices, flags; unsigned char queue, pad[3]; char reserved[64]; };

#define SKR_SEQ_CLIENT_ID        _IOR('S', 0x01, int)
#define SKR_SEQ_CREATE_PORT      _IOWR('S', 0x20, skrseq::PortInfo)
#define SKR_SEQ_SUBSCRIBE        _IOW('S', 0x30, skrseq::Subscribe)
#define SKR_SEQ_NEXT_CLIENT      _IOWR('S', 0x51, skrseq::ClientInfo)
#define SKR_SEQ_NEXT_PORT        _IOWR('S', 0x52, skrseq::PortInfo)

enum : unsigned char { kNoteOn = 6, kNoteOff = 7, kController = 10, kQueueDirect = 253 };
enum : unsigned { kCapRead = 1u << 0, kCapWrite = 1u << 1, kCapSubsRead = 1u << 5, kCapSubsWrite = 1u << 6,
                  kTypeMidiGeneric = 1u << 1, kTypeApplication = 1u << 20, kLenVariable = 1u << 2, kLenMask = 3u << 2 };

struct Client
{
    int fd = -1, me = -1, myPort = -1;
    Addr dev{0, 0};
    bool haveDev = false, listening = false;
    std::string log;

    ~Client() { close(); }
    void close() { if (fd >= 0) ::close(fd); fd = -1; haveDev = listening = false; }

    // opens the own client + port, then finds the device (name contains `want`) and listens to it
    bool open(const char* want)
    {
        close(); log.clear();
        fd = ::open("/dev/snd/seq", O_RDWR | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) { log += "kann /dev/snd/seq nicht oeffnen\n"; return false; }
        if (::ioctl(fd, SKR_SEQ_CLIENT_ID, &me) < 0) { log += "CLIENT_ID fehlgeschlagen\n"; close(); return false; }
        PortInfo p; std::memset(&p, 0, sizeof(p));
        p.addr.client = (unsigned char)me;
        std::strncpy(p.name, "SKRATCHA", sizeof(p.name) - 1);
        p.capability = kCapRead | kCapSubsRead | kCapWrite | kCapSubsWrite;
        p.type = kTypeMidiGeneric | kTypeApplication;
        if (::ioctl(fd, SKR_SEQ_CREATE_PORT, &p) < 0) { log += "CREATE_PORT fehlgeschlagen\n"; close(); return false; }
        myPort = p.addr.port;
        log += "eigener Client " + std::to_string(me) + ":" + std::to_string(myPort) + "\n";
        return findDevice(want, true);
    }

    // (re)finds the device; the client number changes when it is plugged in again. Returns true while present.
    bool findDevice(const char* want, bool verbose = false)
    {
        if (fd < 0) return false;
        bool found = false; Addr a{0, 0};
        ClientInfo c; std::memset(&c, 0, sizeof(c)); c.client = -1;
        while (::ioctl(fd, SKR_SEQ_NEXT_CLIENT, &c) >= 0)
        {
            c.name[63] = 0;
            if (verbose) log += "client " + std::to_string(c.client) + " '" + c.name + "'\n";
            PortInfo q; std::memset(&q, 0, sizeof(q)); q.addr.client = (unsigned char)c.client; q.addr.port = 255;
            while (::ioctl(fd, SKR_SEQ_NEXT_PORT, &q) >= 0)
            {
                q.name[63] = 0;
                if (verbose) { char l[160]; std::snprintf(l, sizeof(l), "   port %d:%d '%s' cap %x\n", q.addr.client, q.addr.port, q.name, q.capability); log += l; }
                if (!found && c.client != me && std::strstr(c.name, want) != nullptr && (q.capability & kCapWrite)) { a = q.addr; found = true; }
                if (q.addr.port == 255) break;
            }
        }
        if (!found) { if (verbose) log += "kein Port mit '" + std::string(want) + "' gefunden\n"; haveDev = listening = false; return false; }
        if (haveDev && listening && a.client == dev.client && a.port == dev.port) return true;
        dev = a; haveDev = true;
        Subscribe s; std::memset(&s, 0, sizeof(s));
        s.sender = dev; s.dest.client = (unsigned char)me; s.dest.port = (unsigned char)myPort;
        listening = ::ioctl(fd, SKR_SEQ_SUBSCRIBE, &s) >= 0 || errno == EBUSY;
        log += "Ziel " + std::to_string(dev.client) + ":" + std::to_string(dev.port) + (listening ? ", mithoeren OK\n" : ", mithoeren geht nicht\n");
        return true;
    }

    bool sendEv(Event& e)
    {
        if (fd < 0 || !haveDev) return false;
        e.flags = 0; e.queue = kQueueDirect;
        e.source.client = (unsigned char)me; e.source.port = (unsigned char)myPort; e.dest = dev;
        for (int i = 0; i < 20; ++i) { if (::write(fd, &e, sizeof(e)) == (ssize_t)sizeof(e)) return true; ::usleep(2000); }
        return false;
    }
    bool note(int ch, int n, int vel)
    {
        Event e; std::memset(&e, 0, sizeof(e));
        e.type = vel > 0 ? kNoteOn : kNoteOff; e.data.note.channel = (unsigned char)ch; e.data.note.note = (unsigned char)n; e.data.note.velocity = (unsigned char)vel;
        return sendEv(e);
    }
    bool cc(int ch, int num, int val)
    {
        Event e; std::memset(&e, 0, sizeof(e));
        e.type = kController; e.data.control.channel = (unsigned char)ch; e.data.control.param = (unsigned)num; e.data.control.value = val;
        return sendEv(e);
    }
    // reads everything that arrived and hands it over as plain MIDI bytes (note on/off, controller, pitch bend)
    template <class F> int readMidi(F&& fn)
    {
        if (fd < 0 || !listening) return 0;
        int n = 0; unsigned char buf[8192];
        for (;;)
        {
            const ssize_t got = ::read(fd, buf, sizeof(buf));
            if (got <= 0) break;
            ssize_t off = 0;
            while (off + (ssize_t)sizeof(Event) <= got)
            {
                Event e; std::memcpy(&e, buf + off, sizeof(e)); off += sizeof(e);
                if ((e.flags & kLenMask) == kLenVariable) { off += e.data.raw32[0]; continue; }
                if (e.source.client != dev.client) continue;
                const int ch = e.data.note.channel & 15;
                if (e.type == kNoteOn) fn((uint8_t)(0x90 | ch), e.data.note.note, e.data.note.velocity);
                else if (e.type == kNoteOff) fn((uint8_t)(0x80 | ch), e.data.note.note, e.data.note.velocity);
                else if (e.type == kController) fn((uint8_t)(0xB0 | (e.data.control.channel & 15)), (uint8_t)(e.data.control.param & 127), (uint8_t)(e.data.control.value & 127));
                else if (e.type == 13) { const int v = e.data.control.value + 8192; fn((uint8_t)(0xE0 | (e.data.control.channel & 15)), (uint8_t)(v & 127), (uint8_t)((v >> 7) & 127)); }
                else continue;
                ++n;
            }
        }
        return n;
    }
    // signed platter movement (CC55 high byte, CC54 low byte, channel 1) since the last call
    int drainSigned()
    {
        int sum = 0, msb = 0;
        readMidi([&](uint8_t st, uint8_t d1, uint8_t d2) {
            if ((st & 0xF0) != 0xB0 || (st & 15) != 0) return;
            if (d1 == 55) msb = d2;
            else if (d1 == 54) { int v = msb * 128 + d2; if (v >= 8192) v -= 16384; sum += v; }
        });
        return sum;
    }
    // reads what the device sent; returns the number of platter frames (controller 54/55)
    int drainPlatter()
    {
        if (fd < 0 || !listening) return 0;
        int frames = 0; unsigned char buf[4096];
        for (;;)
        {
            const ssize_t n = ::read(fd, buf, sizeof(buf));
            if (n <= 0) break;
            ssize_t off = 0;
            while (off + (ssize_t)sizeof(Event) <= n)
            {
                Event e; std::memcpy(&e, buf + off, sizeof(e)); off += sizeof(e);
                if ((e.flags & kLenMask) == kLenVariable) off += e.data.raw32[0];
                if (e.type == kController && (e.data.control.param == 54 || e.data.control.param == 55)) ++frames;
            }
        }
        return frames;
    }
};
} // namespace skrseq
