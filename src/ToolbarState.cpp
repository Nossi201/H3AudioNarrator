#include "ToolbarState.hpp"

ToolbarState g_toolbar;

ToolbarState::ToolbarState()
    : defsLoaded(false), colorPlayer(-1), packLodsLoaded(false),
      ready(false), boundAdventureDlg(nullptr),
      absX(-1), absY(-1), w(0), h(0), dateTextAdjusted(false)
{
    // Spin count 400 — optymalne dla krotkiego contention na 4-elementowej tablicy
    InitializeCriticalSectionAndSpinCount(&cs, 400);
}

ToolbarState::~ToolbarState()
{
    DeleteCriticalSection(&cs);
}

void ToolbarState::SafeSetPressed(int idx, bool val)
{
    EnterCriticalSection(&cs);
    btns[idx].pressed = val;
    LeaveCriticalSection(&cs);
}

bool ToolbarState::SafeGetPressed(int idx) const
{
    // const_cast bezpieczny — CRITICAL_SECTION jest mutable semantycznie
    EnterCriticalSection(const_cast<CRITICAL_SECTION*>(&cs));
    bool v = btns[idx].pressed;
    LeaveCriticalSection(const_cast<CRITICAL_SECTION*>(&cs));
    return v;
}

void ToolbarState::SafeClearAllPressed(bool* changedOut)
{
    bool changed = false;
    EnterCriticalSection(&cs);
    for (int i = 0; i < TOOLBAR_BTN_COUNT; i++)
        if (btns[i].pressed) { btns[i].pressed = false; changed = true; }
    LeaveCriticalSection(&cs);
    if (changedOut) *changedOut = changed;
}
