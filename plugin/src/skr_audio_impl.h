// skr_audio_impl.h - included once (SKRATCHA.cpp): the decoder implementations.
#pragma once
#include "skr_audio.h"

#if defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"
#pragma GCC diagnostic ignored "-Wsign-compare"
#pragma GCC diagnostic ignored "-Wunused-parameter"
#pragma GCC diagnostic ignored "-Wunused-variable"
#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"
#pragma GCC diagnostic ignored "-Wshadow"
#pragma GCC diagnostic ignored "-Wcast-align"
#endif
#define DR_WAV_IMPLEMENTATION
#define DR_WAV_NO_WCHAR
#define DR_MP3_IMPLEMENTATION
#define DR_MP3_NO_SIMD
#define DR_FLAC_IMPLEMENTATION
#define DR_FLAC_NO_SIMD
#define DR_FLAC_NO_OGG
#define DR_FLAC_NO_WCHAR
#define DR_MP3_NO_WCHAR
#include "third_party/dr_wav.h"
#include "third_party/dr_mp3.h"
#include "third_party/dr_flac.h"
#if defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

namespace skr {

namespace detail {
inline void split(const float* inter, size_t frames, unsigned ch, double rate, AudioData& out)
{
    out.sampleRate = rate > 1000.0 ? rate : 44100.0;
    out.l.resize(frames);
    if (ch >= 2) out.r.resize(frames); else out.r.clear();
    for (size_t i = 0; i < frames; ++i)
    {
        float a = inter[i * ch], b = ch >= 2 ? inter[i * ch + 1] : a;
        out.l[i] = std::isfinite(a) ? a : 0.0f;
        if (ch >= 2) out.r[i] = std::isfinite(b) ? b : 0.0f;
    }
}
} // namespace detail

inline bool decodeAudio(const std::string& path, double maxSeconds, AudioData& out)
{
    const std::string e = lowerExt(path);
    std::vector<float> buf;
    if (e == "mp3")
    {
        drmp3 mp3;
        if (!drmp3_init_file(&mp3, path.c_str(), nullptr)) return false;
        const unsigned ch = mp3.channels ? mp3.channels : 1;
        const size_t want = (size_t)(maxSeconds * mp3.sampleRate) + 1;
        buf.resize(want * ch);
        const size_t got = (size_t)drmp3_read_pcm_frames_f32(&mp3, want, buf.data());
        const double rate = mp3.sampleRate;
        drmp3_uninit(&mp3);
        if (got < 16) return false;
        detail::split(buf.data(), got, ch, rate, out);
        return true;
    }
    if (e == "flac")
    {
        drflac* f = drflac_open_file(path.c_str(), nullptr);
        if (f == nullptr) return false;
        const unsigned ch = f->channels ? f->channels : 1;
        const size_t want = (size_t)(maxSeconds * f->sampleRate) + 1;
        buf.resize(want * ch);
        const size_t got = (size_t)drflac_read_pcm_frames_f32(f, want, buf.data());
        const double rate = f->sampleRate;
        drflac_close(f);
        if (got < 16) return false;
        detail::split(buf.data(), got, ch, rate, out);
        return true;
    }
    // WAV (all the odd flavours: float, 8-64 bit, extensible, ADPCM, RF64) and AIFF / AIFC
    drwav w;
    if (!drwav_init_file(&w, path.c_str(), nullptr)) return false;
    const unsigned ch = w.channels ? w.channels : 1;
    const size_t want = (size_t)(maxSeconds * w.sampleRate) + 1;
    buf.resize(want * ch);
    const size_t got = (size_t)drwav_read_pcm_frames_f32(&w, want, buf.data());
    const double rate = w.sampleRate;
    drwav_uninit(&w);
    if (got < 16) return false;
    detail::split(buf.data(), got, ch, rate, out);
    return true;
}

} // namespace skr
