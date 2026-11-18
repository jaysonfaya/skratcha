// skr_feed.h - the audio link between SKRATCHA FEED (an insert effect on any track or the master)
// and SKRATCHA (the turntables). Shared by both plugins; keep the two copies identical.
//
// One link per channel (1..4) lives in POSIX shared memory ("/skratcha_feed_<n>", tmpfs, gone after a
// reboot; fallback: a file in /tmp). Nothing is written anywhere else on the MPC.
//
//   capture ring : FEED writes every input frame here (the track as it plays)
//   return ring  : while SKRATCHA scratches this channel LIVE, it writes the scratched audio here at the
//                  same timeline position; FEED plays it instead of the dry track (after `latency` frames)
//
// Single writer per ring, lock-free: data first, then the position with release order.
#pragma once

#include <atomic>
#include <cstdint>
#include <cstring>
#include <string>

#if !defined(_WIN32)
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace skrfeed {

constexpr uint32_t kMagic = 0x464b5253u;      // "SRKF"
constexpr uint32_t kVersion = 1;
constexpr int kChannels = 4;
constexpr uint32_t kCapFrames = 1u << 19;     // capture: 11.9 s at 44.1 kHz, 10.9 s at 48 kHz
constexpr uint32_t kRetFrames = 1u << 14;     // return: 0.37 s
constexpr uint32_t kCapMask = kCapFrames - 1, kRetMask = kRetFrames - 1;

struct Header
{
    uint32_t magic, version, capFrames, retFrames;
    std::atomic<uint32_t> sampleRate;
    std::atomic<uint32_t> latency;            // FEED: how far behind it reads the return ring (frames)
    std::atomic<uint64_t> writePos;           // FEED: capture frames written so far (monotonic)
    std::atomic<uint32_t> feedAlive;          // FEED: +1 per block
    std::atomic<uint32_t> users;              // FEED instances on this channel
    std::atomic<uint32_t> replaceMode;        // FEED: 1 = play the return instead of the track while LIVE
    std::atomic<uint32_t> liveOn;             // SKRATCHA: 1 while it scratches this channel live
    std::atomic<uint32_t> skrAlive;           // SKRATCHA: +1 per block while live
    std::atomic<uint64_t> retPos;             // SKRATCHA: return frames written up to this timeline position
    std::atomic<uint32_t> peak;               // FEED: input peak * 1000 (for the meter)
    char pad[64];
};

struct Shared
{
    Header h;
    float cap[kCapFrames * 2];                // interleaved L R
    float ret[kRetFrames * 2];
};

inline std::string shmName(int ch) { return "/skratcha_feed_" + std::to_string(ch + 1); }
inline std::string tmpName(int ch) { return "/tmp/skratcha_feed_" + std::to_string(ch + 1); }

// Maps channel ch. create = true (FEED) makes it if missing; SKRATCHA only opens an existing one.
inline Shared* mapChannel(int ch, bool create)
{
#if defined(_WIN32)
    (void)ch; (void)create; return nullptr;
#else
    const size_t size = sizeof(Shared);
    int fd = shm_open(shmName(ch).c_str(), O_RDWR | (create ? O_CREAT : 0), 0666);
    if (fd < 0) fd = open(tmpName(ch).c_str(), O_RDWR | (create ? O_CREAT : 0), 0666);
    if (fd < 0) return nullptr;
    struct stat st;
    if (fstat(fd, &st) != 0) { close(fd); return nullptr; }
    if ((size_t)st.st_size < size)
    {
        if (!create || ftruncate(fd, (off_t)size) != 0) { close(fd); return nullptr; }
    }
    void* p = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (p == MAP_FAILED) return nullptr;
    Shared* s = static_cast<Shared*>(p);
    if (create && (s->h.magic != kMagic || s->h.version != kVersion))
    {
        std::memset(static_cast<void*>(&s->h), 0, sizeof(Header));
        s->h.capFrames = kCapFrames; s->h.retFrames = kRetFrames; s->h.version = kVersion;
        s->h.sampleRate.store(44100); s->h.replaceMode.store(1);
        std::atomic_thread_fence(std::memory_order_release);
        s->h.magic = kMagic;
    }
    if (s->h.magic != kMagic || s->h.version != kVersion || s->h.capFrames != kCapFrames) { munmap(p, size); return nullptr; }
    return s;
#endif
}

inline void unmapChannel(Shared* s)
{
#if !defined(_WIN32)
    if (s != nullptr) munmap(static_cast<void*>(s), sizeof(Shared));
#else
    (void)s;
#endif
}

inline void removeChannel(int ch)
{
#if !defined(_WIN32)
    shm_unlink(shmName(ch).c_str());
    unlink(tmpName(ch).c_str());
#else
    (void)ch;
#endif
}

} // namespace skrfeed
