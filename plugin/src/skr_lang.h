// skr_lang.h - SKRATCHA language switch: German screen texts -> English (table: skr_lang_table.h, from tools/lang_en.py)
#pragma once
#include <cstring>
#include <string>
#include "skr_lang_table.h"

namespace skrlang {
inline bool isWordChar(char c) { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'); }
inline bool isLetter(char c) { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z'); }

inline std::string toEn(const std::string& s)
{
    for (const Pair& p : kFull) if (s == p.de) return p.en;
    // the same with surrounding blanks
    const size_t a = s.find_first_not_of(' '), b = s.find_last_not_of(' ');
    if (a != std::string::npos)
    {
        const std::string core = s.substr(a, b - a + 1);
        for (const Pair& p : kFull) if (core == p.de) return s.substr(0, a) + p.en + s.substr(b + 1);
    }
    std::string out = s;
    for (const Pair& p : kPhrases)
    {
        const size_t n = std::strlen(p.de);
        size_t pos = 0;
        while ((pos = out.find(p.de, pos)) != std::string::npos)
        {
            const bool okL = pos == 0 || !isWordChar(out[pos - 1]);
            const bool okR = pos + n >= out.size() || !isLetter(out[pos + n]);
            if (okL && okR) { out.replace(pos, n, p.en); pos += std::strlen(p.en); }
            else pos += n;
        }
    }
    return out;
}
} // namespace skrlang
