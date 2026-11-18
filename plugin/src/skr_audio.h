// skr_audio.h - SKRATCHA: reads WAV, AIFF, MP3 and FLAC (only the first seconds that are needed).
//
// Decoders: dr_wav, dr_mp3, dr_flac by David Reid (third_party/, public domain / MIT No Attribution).
// Runs on the loader thread only, never on the audio thread.
#pragma once

#include <cctype>
#include <cmath>
#include <string>
#include <vector>

namespace skr {

struct AudioData
{
    double sampleRate = 44100.0;
    std::vector<float> l, r;      // r empty = mono
};

inline std::string lowerExt(const std::string& f)
{
    const size_t dot = f.find_last_of('.');
    if (dot == std::string::npos) return std::string();
    std::string e = f.substr(dot + 1);
    for (char& c : e) c = (char)std::tolower((unsigned char)c);
    return e;
}

inline bool isAudioName(const std::string& f)
{
    if (f.empty() || f[0] == '.') return false;   // hidden files and macOS "._" shadows
    const std::string e = lowerExt(f);
    return e == "wav" || e == "wave" || e == "aif" || e == "aiff" || e == "aifc" || e == "mp3" || e == "flac";
}


} // namespace skr
