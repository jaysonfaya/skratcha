// skr_record.h - SKRATCHA: records (band-limited sample mip-maps), WAV loading and the drive browser index.
//
// SPDX-License-Identifier: MIT
//
// Nothing in here runs on the audio thread except Record reads (readAt / readLevel in SKRATCHA.cpp).
#pragma once

#include "mpc_plugin.h"
#include "dsp/wav.h"
#include "skr_audio_impl.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

#if defined(_WIN32)
  #include <io.h>
#else
  #include <dirent.h>
  #include <glob.h>
  #include <sys/stat.h>
#endif

namespace skr {

constexpr double kPi = 3.14159265358979323846;
constexpr int    kMipLevels = 6;          // 1x, 2x, 4x, 8x, 16x, 32x
constexpr double kMaxSeconds = 15.0;      // per slot (16 slots in memory): longer files are cut

// ---- one loaded record ---------------------------------------------------------------------------------------
struct Record
{
    std::string name;                          // display name
    std::string path;                          // where it came from (state, browser)
    double sampleRate = 44100.0;
    int channels = 1;
    size_t length = 0;                         // level-0 frames
    std::vector<float> lv[kMipLevels][2];      // [level][channel]
    size_t len[kMipLevels] = {0, 0, 0, 0, 0, 0};
};

// A 31-tap windowed-sinc low-pass at a quarter of the sample rate (half of Nyquist), for 2:1 decimation.
struct HalfbandFir
{
    static constexpr int N = 31;
    float h[N];
    HalfbandFir()
    {
        const double fc = 0.225;
        double sum = 0.0;
        for (int i = 0; i < N; ++i)
        {
            const double m = i - (N - 1) * 0.5;
            const double sinc = (m == 0.0) ? 2.0 * fc : std::sin(2.0 * kPi * fc * m) / (kPi * m);
            const double w = 0.42 - 0.5 * std::cos(2.0 * kPi * i / (N - 1)) + 0.08 * std::cos(4.0 * kPi * i / (N - 1));
            h[i] = (float)(sinc * w); sum += h[i];
        }
        for (int i = 0; i < N; ++i) h[i] = (float)(h[i] / sum);
    }
};

inline void buildMips(Record& r)
{
    static const HalfbandFir fir;
    constexpr int N = HalfbandFir::N, H = (N - 1) / 2;
    for (int k = 1; k < kMipLevels; ++k)
    {
        const size_t srcLen = r.len[k - 1];
        const size_t dstLen = (srcLen + 1) / 2;
        r.len[k] = dstLen;
        for (int c = 0; c < r.channels; ++c)
        {
            const std::vector<float>& s = r.lv[k - 1][c];
            std::vector<float>& d = r.lv[k][c];
            d.assign(dstLen, 0.0f);
            const float* sp = s.data();
            for (size_t j = 0; j < dstLen; ++j)
            {
                const long centre = (long)(2 * j);
                float acc;
                if (centre >= H && centre + H < (long)srcLen)
                {
                    // symmetric taps: fold the two halves, half the multiplies
                    const float* p = sp + centre;
                    acc = fir.h[H] * p[0];
                    for (int t = 1; t <= H; ++t) acc += fir.h[H + t] * (p[t] + p[-t]);
                }
                else
                {
                    acc = 0.0f;
                    for (int t = 0; t < N; ++t)
                    {
                        const long idx = centre + t - H;
                        if (idx >= 0 && idx < (long)srcLen) acc += fir.h[t] * sp[idx];
                    }
                }
                d[j] = std::fabs(acc) < 1e-20f ? 0.0f : acc;
            }
        }
    }
}

inline std::string fileOf(const std::string& path)
{
    const size_t s = path.find_last_of("/\\");
    return s == std::string::npos ? path : path.substr(s + 1);
}

inline std::string displayName(const std::string& file, size_t maxLen = 22)
{
    std::string s = file;
    const size_t dot = s.find_last_of('.');
    if (dot != std::string::npos) s = s.substr(0, dot);
    if (s.size() > 3 && std::isdigit((unsigned char)s[0]) && std::isdigit((unsigned char)s[1]) && (s[2] == ' ' || s[2] == '_' || s[2] == '-'))
        s = s.substr(3);
    for (char& ch : s) { if (ch == '_') ch = ' '; else ch = (char)std::toupper((unsigned char)ch); }
    if (s.size() > maxLen) s = s.substr(0, maxLen);
    return s;
}

// Loads a WAV (mono or stereo, any sample rate the SDK reader takes), cuts it to maxSeconds and builds the mips.
inline Record* loadRecord(const std::string& path, double maxSeconds = kMaxSeconds)
{
    AudioData a;
    if (!decodeAudio(path, maxSeconds, a) || a.l.size() < 16) return nullptr;
    Record* r = new Record();
    r->path = path;
    r->name = displayName(fileOf(path));
    r->sampleRate = a.sampleRate;
    r->channels = a.r.empty() ? 1 : 2;
    const size_t n = a.l.size();
    r->length = n;
    r->len[0] = n;
    r->lv[0][0] = std::move(a.l);
    if (r->channels > 1) r->lv[0][1] = std::move(a.r);
    for (int c = 0; c < r->channels; ++c)
    {
        // 2 ms fade-in / fade-out so a one-shot never clicks at its ends when it is scratched past them
        const size_t f = std::min(n / 4, (size_t)(0.002 * r->sampleRate));
        for (size_t i = 0; i < f; ++i) { const float g = (float)i / (float)f; r->lv[0][c][i] *= g; r->lv[0][c][n - 1 - i] *= g; }
    }
    buildMips(*r);
    return r;
}

inline bool hasWavExt(const std::string& f)
{
    return isAudioName(f);
}

inline bool hasWavExtOld(const std::string& f)
{
    if (f.size() < 5 || f[0] == '.') return false;
    std::string e = f.substr(f.size() - 4);
    for (char& ch : e) ch = (char)std::tolower((unsigned char)ch);
    return e == ".wav";
}

inline bool lessNoCase(const std::string& a, const std::string& b)
{
    const size_t n = std::min(a.size(), b.size());
    for (size_t i = 0; i < n; ++i)
    {
        const int ca = std::tolower((unsigned char)a[i]), cb = std::tolower((unsigned char)b[i]);
        if (ca != cb) return ca < cb;
    }
    return a.size() < b.size();
}

inline void listWavs(const std::string& dir, std::vector<std::string>& out)
{
    std::vector<std::string> found;
#if defined(_WIN32)
    struct _finddata_t fd;
    intptr_t h = _findfirst((dir + "/*.wav").c_str(), &fd);
    if (h != -1)
    {
        do { if (!(fd.attrib & _A_SUBDIR) && hasWavExt(fd.name)) found.push_back(dir + "/" + fd.name); } while (_findnext(h, &fd) == 0);
        _findclose(h);
    }
#else
    if (DIR* d = opendir(dir.c_str()))
    {
        while (dirent* e = readdir(d))
            if (hasWavExt(e->d_name)) found.push_back(dir + "/" + e->d_name);
        closedir(d);
    }
#endif
    std::sort(found.begin(), found.end(), lessNoCase);
    out.insert(out.end(), found.begin(), found.end());
}

// ---- the drive browser index -----------------------------------------------------------------------------------
// Every folder that holds WAV files, found by walking the drives (depth and count limited, hidden folders skipped).
struct BrowserFolder
{
    std::string path;                       // absolute
    std::string label;                      // "DRIVE › Samples › Vox"
    std::vector<std::string> files;         // file names (not paths), sorted
};

struct BrowserIndex
{
    std::vector<BrowserFolder> folders;
    static constexpr int kMaxFolders = 1500;
    static constexpr int kMaxFilesPerFolder = 4000;
    static constexpr int kMaxDepth = 7;
    int visitedDirs = 0;

    void addFolder(const std::string& path, const std::string& label)
    {
        if ((int)folders.size() >= kMaxFolders) return;
        BrowserFolder f; f.path = path; f.label = label;
#if !defined(_WIN32)
        if (DIR* d = opendir(path.c_str()))
        {
            while (dirent* e = readdir(d)) if (hasWavExt(e->d_name)) f.files.push_back(e->d_name);
            closedir(d);
        }
#else
        std::vector<std::string> p; listWavs(path, p); for (auto& s : p) f.files.push_back(fileOf(s));
#endif
        if (f.files.empty()) return;
        std::sort(f.files.begin(), f.files.end(), lessNoCase);
        if ((int)f.files.size() > kMaxFilesPerFolder) f.files.resize(kMaxFilesPerFolder);
        for (const BrowserFolder& g : folders) if (g.path == f.path) return;
        folders.push_back(std::move(f));
    }

    // walk a tree; label = what the user sees for the root ("SSD", "SD CARD", ...)
    void walk(const std::string& root, const std::string& label, int depth = 0)
    {
#if !defined(_WIN32)
        if (depth > kMaxDepth || (int)folders.size() >= kMaxFolders || visitedDirs > 20000) return;
        ++visitedDirs;
        addFolder(root, label);
        std::vector<std::string> subs;
        if (DIR* d = opendir(root.c_str()))
        {
            while (dirent* e = readdir(d))
            {
                const std::string n = e->d_name;
                if (n.empty() || n[0] == '.' || n == "lost+found" || n == "System Volume Information" || n == "$RECYCLE.BIN") continue;
                bool isDir = e->d_type == DT_DIR;
                if (e->d_type == DT_UNKNOWN)
                {
                    struct stat st;
                    if (stat((root + "/" + n).c_str(), &st) == 0) isDir = S_ISDIR(st.st_mode);
                }
                if (isDir) subs.push_back(n);
            }
            closedir(d);
        }
        std::sort(subs.begin(), subs.end(), lessNoCase);
        for (const std::string& s : subs) walk(root + "/" + s, label + " > " + s, depth + 1);
#else
        addFolder(root, label); (void)depth;
#endif
    }

    void scan(const std::string& builtIn, const std::string& mySamples)
    {
        folders.clear(); visitedDirs = 0;
        addFolder(builtIn, "SKRATCHA SAMPLES");
        if (!mySamples.empty()) walk(mySamples, "MY SAMPLES");
#if !defined(_WIN32)
        std::vector<std::pair<std::string, std::string>> roots;
        glob_t g;
        if (glob("/media/*", 0, nullptr, &g) == 0)
        {
            for (size_t i = 0; i < g.gl_pathc; ++i) { std::string p = g.gl_pathv[i]; roots.push_back({p, displayName(fileOf(p), 14)}); }
            globfree(&g);
        }
        for (const char* p : {"/nvme", "/sdcard", "/mnt/usb", "/run/media"})
        {
            struct stat st;
            if (stat(p, &st) == 0 && S_ISDIR(st.st_mode)) roots.push_back({p, displayName(fileOf(p), 14)});
        }
        for (auto& r : roots) walk(r.first, r.second);
#endif
    }
};

inline float hermite(float xm1, float x0, float x1, float x2, float t)
{
    const float c1 = 0.5f * (x1 - xm1);
    const float c2 = xm1 - 2.5f * x0 + 2.0f * x1 - 0.5f * x2;
    const float c3 = 0.5f * (x2 - xm1) + 1.5f * (x0 - x1);
    return ((c3 * t + c2) * t + c1) * t + x0;
}

} // namespace skr
