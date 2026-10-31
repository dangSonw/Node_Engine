#include "runtime.hpp"
namespace rt {
void QuitApplication(Ctx& c) { c.quit_requested=true; CancelSceneChange(c); }
void FinishApplication(Ctx& c,const std::function<void()>& on_quit,
                       const std::function<void()>& update_ui,const std::function<void()>& process_save) {
    if(c.quit_dispatched) return;
    if(c.execution_depth || c.call_depth || !c.parameters.empty())
        throw std::runtime_error("Application shutdown requires a graph execution boundary");
    c.quit_requested=c.quit_dispatched=true;
    CancelSceneChange(c);
    c.remaining=c.budget;
    on_quit(); DrainEvents(c);
    for(unsigned saves=0;;++saves) {
        update_ui(); DrainUiEvents(c); DrainEvents(c);
        if(!GameSavePending(c)) break;
        if(saves==64) throw std::runtime_error("Application shutdown exceeded 64 pending save requests");
        process_save();
    }
}
}
