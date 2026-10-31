#pragma once
#include <functional>
namespace rt {
struct Ctx;
void QuitApplication(Ctx&);
// Hosts invoke this at a graph/frame boundary, before releasing native resources.
void FinishApplication(Ctx&,const std::function<void()>& on_quit,
                       const std::function<void()>& update_ui,const std::function<void()>& process_save);
}
