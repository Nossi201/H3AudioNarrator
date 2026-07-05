#pragma once
#include "ToolbarState.hpp"

namespace h3 { struct H3BaseDlg; struct H3Msg; }

// Usuwa stan wcisnięcia ze wszystkich przycisków i zleca przerysowanie (jeśli było).
void ClearToolbarPressed();

// Wykonuje akcję powiązaną z przyciskiem toolbara (Play/Pause, Prev, Next, Menu).
void ExecuteToolbarAction(ToolbarButtonKind kind);

// Obsługuje zdarzenia myszy z H3BaseDlg (fallback gdy WH_MOUSE_LL niedostępny).
void HandleToolbarMouse(h3::H3BaseDlg* dlg, h3::H3Msg* msg);
