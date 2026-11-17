// skr_helper.h - SKRATCHA: the scratch teacher.
//
// SPDX-License-Identifier: MIT
//
// A lesson is one bar of eight 1/8-note steps:
//   * a ghost path: where the hand should be on the strip at each step boundary (-1 .. +1 strip units),
//   * a fader pattern: open (1), closed (0) or don't care (-1) for each half step.
// While a lesson runs the teacher ticks a metronome, moves the ghost (the green dot on the strip picture), and at
// the end of every step compares what the record really did (how far, which way) and whether the deck was audible
// with the pattern. After every bar it picks the most useful tip; after four bars it gives 0..3 stars.
// DEMO lets the teacher play the pattern itself on the active deck, so you hear how it should sound.
//
// Everything here runs on the audio thread: fixed-size, no allocation.
#pragma once

#include <cmath>
#include <cstdint>

namespace skr {

constexpr int kNumLessons = 6;
constexpr int kSteps = 8;

struct Lesson
{
    const char* name;
    const char* line1;
    const char* line2;
    float bpm;                  // suggested tempo (the BPM knob starts here when the lesson is chosen)
    float path[kSteps + 1];     // hand position at the step boundaries, strip units
    int8_t fader[kSteps * 2];   // per half step: 1 open, 0 closed, -1 any
    bool openMode;              // the CUT pad works as "hold = sound" for this lesson
};

// The order is the learning path: each lesson adds one new skill.
static const Lesson kLessons[kNumLessons] = {
    {"1 BABY SCRATCH", "VOR UND ZURUECK IM TAKT",
     "FOLGE DEM GRUENEN PUNKT", 80.0f,
     {-0.7f, 0.7f, -0.7f, 0.7f, -0.7f, 0.7f, -0.7f, 0.7f, -0.7f},
     {-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1}, false},
    {"2 DRAG", "4 SCHLAEGE VOR, 4 ZURUECK",
     "LANGSAM UND GLEICHMAESSIG", 76.0f,
     {-0.8f, -0.4f, 0.0f, 0.4f, 0.8f, 0.4f, 0.0f, -0.4f, -0.8f},
     {-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1}, false},
    {"3 FORWARD", "VOR-ZUG: PAD 10 HALTEN = TON",
     "ZURUECK: LOSLASSEN = STILL", 78.0f,
     {-0.7f, 0.7f, -0.7f, 0.7f, -0.7f, 0.7f, -0.7f, 0.7f, -0.7f},
     {1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0}, true},
    {"4 CHIRP", "JEDER ZUG: TON AN, DANN AUS",
     "VOR UND ZURUECK - WIE EIN VOGEL", 82.0f,
     {-0.7f, 0.7f, -0.7f, 0.7f, -0.7f, 0.7f, -0.7f, 0.7f, -0.7f},
     {1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0}, true},
    {"5 TRANSFORMER", "PLATTE LANGSAM ZIEHEN",
     "PAD 10 SCHNELL TIPPEN: AN-AUS", 72.0f,
     {-0.8f, -0.4f, 0.0f, 0.4f, 0.8f, 0.4f, 0.0f, -0.4f, -0.8f},
     {1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0}, true},
    {"6 TEAR", "VOR IN EINEM ZUG",
     "ZURUECK IN ZWEI, KURZE PAUSE", 80.0f,
     {-0.7f, 0.7f, 0.0f, 0.0f, -0.7f, 0.7f, 0.0f, 0.0f, -0.7f},
     {-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1}, false},
};

// tips (index = message id)
enum Msg
{
    kMsgIdle = 0, kMsgCountIn, kMsgTouch, kMsgGreat, kMsgDirection, kMsgMore, kMsgLess, kMsgFader, kMsgStill,
    kMsgStars3, kMsgAlmost, kMsgDemo, kMsgMotor, kMsgSilent, kMsgGood, kMsgNoRecord,
    kNumMsgs
};

static const char* const kMsgText[kNumMsgs] = {    // max 31 characters (MPC value text)
    "LEKTION WAEHLEN, DANN START",
    "ZAEHL MIT: 1 - 2 - 3 - 4",
    "BERUEHRE DEN TOUCH STRIP",
    "SUPER! GENAU IM TAKT",
    "FALSCHE RICHTUNG - FOLGE GRUEN",
    "MEHR BEWEGUNG - WEITER ZIEHEN",
    "RUHIGER - KUERZERE ZUEGE",
    "TON AN/AUS: SCHAU AUF DIE LED",
    "IN DER PAUSE STILL HALTEN",
    "*** GESCHAFFT! NAECHSTE LEKTION",
    "FAST! NOCH EINE RUNDE",
    "HOER ZU - SO KLINGT ES",
    "ERST MOTOR STOPPEN (PAD 9)",
    "DECK STUMM - CROSSFADER!",
    "GUT! WEITER SO",
    "ERST EIN SAMPLE LADEN",
};

struct Teacher
{
    // ---- settings (set per block) ----
    int lesson = 0;
    double stepLen = 16537.5;    // samples per 1/8 step
    bool running = false, demo = false, click = true;

    // ---- outputs (read by the UI reporter) ----
    float ghost = 0.0f;          // ghost hand position, strip units
    int beat = 0;                // 1..8 = current step, 0 = not running
    bool faderTarget = false;    // should the deck sound right now?
    int msg = kMsgIdle;
    int stars = 0, best[kNumLessons] = {0, 0, 0, 0, 0, 0};
    int scorePct = 0, bar = 0;
    bool starsNew = false;

    // ---- state ----
    double t = 0.0;              // samples since start (count-in included)
    int stepIdx = -1;
    double stepStartX = 0.0;
    int openHalf[2] = {0, 0}, totalHalf[2] = {0, 0};
    bool touched = false, motorWasOn = false, silent = false;
    int barCorrect = 0, errCount[kNumMsgs] = {};
    int sumPct = 0, barsInRound = 0;
    float clickEnv = 0.0f, clickPhase = 0.0f, clickInc = 0.0f;
    bool barTouched = false;

    void start(int l)
    {
        lesson = l < 0 ? 0 : (l >= kNumLessons ? kNumLessons - 1 : l);
        running = true; t = 0.0; stepIdx = -1; bar = 0; barCorrect = 0; sumPct = 0; barsInRound = 0;
        for (int& e : errCount) e = 0;
        msg = demo ? kMsgDemo : kMsgCountIn; stars = 0; scorePct = 0; barTouched = false;
    }
    void stop() { running = false; beat = 0; msg = kMsgIdle; ghost = 0.0f; faderTarget = false; }

    static float ease(float a, float b, float f) { return a + (b - a) * (0.5f - 0.5f * std::cos(3.14159265f * f)); }

    // one sample. x = active deck record position (file samples), handOn = the user touches the record,
    // audible = the active deck is open (fader + crossfader), motorOn = its motor runs, stroke = file samples
    // per strip unit (sign = strip direction), hasRecord = a sample is on the deck.
    // Returns the click sample to mix in.
    float tick(double x, bool handOn, bool audible, bool motorOn, double stroke, bool hasRecord, double sr)
    {
        if (!running) return 0.0f;
        const Lesson& L = kLessons[lesson];
        const double barLen = stepLen * kSteps;
        const bool countIn = t < barLen && !demo;
        const double tt = countIn ? t : t - (demo ? 0.0 : barLen);
        const int s = (int)std::floor(tt / stepLen) % kSteps;
        const double inStep = std::fmod(tt, stepLen) / stepLen;
        const int half = inStep < 0.5 ? 0 : 1;
        float out = 0.0f;

        // metronome on every beat (two steps), accent on the 1
        const double beatPos = std::fmod(t, stepLen * 2.0);
        if (beatPos < 1.0)
        {
            const bool one = std::fmod(t, barLen) < 1.0;
            clickEnv = one ? 0.22f : 0.13f;
            clickInc = (float)((one ? 2400.0 : 1600.0) / sr);
            clickPhase = 0.0f;
        }
        if (clickEnv > 1e-4f)
        {
            clickPhase += clickInc; if (clickPhase > 1.0f) clickPhase -= 1.0f;
            out = click ? clickEnv * std::sin(6.2831853f * clickPhase) : 0.0f;
            clickEnv *= 0.9975f;
        }

        if (countIn)
        {
            beat = 1 + (int)(t / stepLen) % kSteps;
            ghost = L.path[0];
            faderTarget = false;
            msg = kMsgCountIn;
            stepStartX = x;
            t += 1.0;
            return out;
        }

        // ghost & targets
        ghost = ease(L.path[s], L.path[s + 1], (float)inStep);
        const int fp = L.fader[s * 2 + half];
        faderTarget = fp != 0;
        beat = s + 1;

        if (s != stepIdx)
        {
            if (stepIdx >= 0) finishStep(stepIdx, x, stroke);
            stepIdx = s; stepStartX = x;
            openHalf[0] = openHalf[1] = totalHalf[0] = totalHalf[1] = 0;
            touched = false; motorWasOn = false; silent = true;
        }
        ++totalHalf[half];
        if (audible) ++openHalf[half];
        if (handOn) { touched = true; barTouched = true; }
        if (motorOn) motorWasOn = true;
        if (audible) silent = false;
        if (!hasRecord) errCount[kMsgNoRecord] += 1;
        t += 1.0;
        return out;
    }

    void finishStep(int s, double x, double stroke)
    {
        const Lesson& L = kLessons[lesson];
        const double m = L.path[s + 1] - L.path[s];            // expected hand travel, strip units
        const double D = x - stepStartX;                       // what the record did, file samples
        const double full = std::fabs(stroke) * 1.4;          // a full ghost stroke in file samples
        bool ok = true;
        int err = -1;
        if (std::fabs(m) < 0.05)
        {
            if (std::fabs(D) > 0.18 * full) { ok = false; err = kMsgStill; }
        }
        else
        {
            const double E = m * stroke;                          // stroke = file samples per strip unit (signed)
            const double r = D / (E != 0.0 ? E : 1.0);
            if (r < 0.0) { ok = false; err = kMsgDirection; }
            else if (r < 0.35) { ok = false; err = kMsgMore; }
            else if (r > 2.8) { ok = false; err = kMsgLess; }
        }
        for (int h = 0; h < 2 && ok; ++h)
        {
            const int fp = L.fader[s * 2 + h];
            if (fp < 0 || totalHalf[h] == 0) continue;
            const double o = (double)openHalf[h] / (double)totalHalf[h];
            if ((fp == 1 && o < 0.55) || (fp == 0 && o > 0.45)) { ok = false; err = kMsgFader; }
        }
        if (!ok && err == kMsgFader && silent && L.fader[s * 2] < 0) err = kMsgSilent;
        if (motorWasOn) { ok = false; err = kMsgMotor; }
        if (ok) ++barCorrect; else if (err >= 0) ++errCount[err];

        if (s == kSteps - 1) finishBar();
    }

    void finishBar()
    {
        ++bar;
        scorePct = barCorrect * 100 / kSteps;
        if (demo) { msg = kMsgDemo; barCorrect = 0; for (int& e : errCount) e = 0; return; }
        // the most useful tip for this bar
        int worst = -1, worstN = 0;
        const int order[] = {kMsgNoRecord, kMsgMotor, kMsgSilent, kMsgDirection, kMsgFader, kMsgMore, kMsgLess, kMsgStill};
        for (int k : order) if (errCount[k] > worstN) { worst = k; worstN = errCount[k]; }
        if (errCount[kMsgNoRecord] > 0) worst = kMsgNoRecord;
        if (!barTouched) msg = kMsgTouch;
        else if (scorePct >= 88) msg = kMsgGreat;
        else if (worst >= 0) msg = worst;
        else msg = kMsgGood;
        sumPct += scorePct; ++barsInRound;
        if (barsInRound == 4)
        {
            const int avg = sumPct / 4;
            stars = avg >= 85 ? 3 : avg >= 65 ? 2 : avg >= 40 ? 1 : 0;
            if (stars > best[lesson]) best[lesson] = stars;
            starsNew = true;
            if (stars == 3) msg = kMsgStars3;
            else if (stars == 2) msg = kMsgAlmost;
            sumPct = 0; barsInRound = 0;
        }
        barCorrect = 0; barTouched = false;
        for (int& e : errCount) e = 0;
    }
};

} // namespace skr
