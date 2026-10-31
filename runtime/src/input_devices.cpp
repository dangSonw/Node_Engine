#include "runtime.hpp"
#include "input_devices.hpp"

namespace rt {
namespace {
double Normalized(int axis,Sint16 value) { return axis>=4 ? std::max(0,int(value))/32767.0 : value/double(value<0 ? 32768 : 32767); }
}
GamepadDevices::GamepadDevices() {
    if(GamepadAxisNames.size()!=SDL_GAMEPAD_AXIS_COUNT || GamepadButtonNames.size()!=SDL_GAMEPAD_BUTTON_COUNT)
        throw std::runtime_error("SDL gamepad vocabulary changed");
    // Keep hardware samples current while the host separately gates gameplay on focus.
    if(!SDL_SetHintWithPriority(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS,"1",SDL_HINT_OVERRIDE))
        throw std::runtime_error("Cannot enable focused gamepad resampling");
    if(!SDL_InitSubSystem(SDL_INIT_GAMEPAD)) throw std::runtime_error(SDL_GetError());
    try {
        int count=0; auto ids=SDL_GetGamepads(&count);
        if(!ids) throw std::runtime_error(SDL_GetError());
        try { for(int i=0;i<count;++i) open(ids[i]); } catch(...) { SDL_free(ids); throw; }
        SDL_free(ids);
    } catch(...) { for(auto [id,pad]:devices) SDL_CloseGamepad(pad); SDL_QuitSubSystem(SDL_INIT_GAMEPAD); throw; }
}
GamepadDevices::~GamepadDevices() { for(auto [id,pad]:devices) SDL_CloseGamepad(pad); SDL_QuitSubSystem(SDL_INIT_GAMEPAD); }
void GamepadDevices::open(SDL_JoystickID id) {
    if(devices.contains(id)) return;
    if(devices.size()>=16) throw std::runtime_error("At most 16 connected gamepads are supported");
    auto pad=SDL_OpenGamepad(id);
    // A queued arrival may already have been unplugged before it is handled.
    if(pad) devices.emplace(id,pad);
}
void GamepadDevices::close(SDL_JoystickID id) {
    if(auto it=devices.find(id);it!=devices.end()) { SDL_CloseGamepad(it->second); devices.erase(it); }
    std::erase_if(suppressed,[&](const auto& key){return key.first==id;});
}
void GamepadDevices::sample(std::vector<InputEvent>& pending,SDL_JoystickID only) {
    std::erase_if(suppressed,[&](const auto& key){return !only || key.first==only;});
    for(const auto& [id,pad]:devices) {
        if(only && only!=id) continue;
        pending.push_back(InputEvent::Controller(id,true));
        for(int i=0;i<SDL_GAMEPAD_AXIS_COUNT;++i)
            pending.push_back(InputEvent::Axis(id,GamepadAxisNames.at(i),active ? Normalized(i,SDL_GetGamepadAxis(pad,SDL_GamepadAxis(i))) : 0));
        for(int i=0;i<SDL_GAMEPAD_BUTTON_COUNT;++i) if(SDL_GetGamepadButton(pad,SDL_GamepadButton(i))) suppressed.emplace(id,i);
    }
}
void GamepadDevices::reset(Ctx& c,bool focused) {
    active=focused; c.input.gamepads.clear();
    std::vector<InputEvent> sampled; sample(sampled); AdvanceInput(c,sampled);
}
void GamepadDevices::sync(bool enabled,std::vector<InputEvent>& pending) {
    if(active==enabled) return;
    active=enabled;
    if(active) sample(pending);
    else for(const auto& [id,pad]:devices) {
        // Focus reconciliation must not release a mouse click that just focused the viewport.
        pending.push_back(InputEvent::Controller(id,false));
        pending.push_back(InputEvent::Controller(id,true));
    }
}
void GamepadDevices::event(const SDL_Event& e,bool collect,std::vector<InputEvent>& pending) {
    if(e.type==SDL_EVENT_GAMEPAD_ADDED) {
        auto id=e.gdevice.which; const bool existing=devices.contains(id); open(id);
        if(collect && devices.contains(id)) {
            if(existing) pending.push_back(InputEvent::Controller(id,true)); else sample(pending,id);
        }
    } else if(e.type==SDL_EVENT_GAMEPAD_REMOVED) {
        auto id=e.gdevice.which; close(id);
        if(collect) pending.push_back(InputEvent::Controller(id,false));
    } else if(e.type==SDL_EVENT_GAMEPAD_REMAPPED) {
        if(collect && devices.contains(e.gdevice.which)) {
            pending.push_back(InputEvent::Controller(e.gdevice.which,false));
            pending.push_back(InputEvent::Controller(e.gdevice.which,true));
            // Mapping changes must not retain held buttons from the old layout.
            sample(pending,e.gdevice.which);
        }
    } else if(e.type==SDL_EVENT_GAMEPAD_AXIS_MOTION) {
        const auto& a=e.gaxis;
        if(collect && active && devices.contains(a.which) && a.axis<SDL_GAMEPAD_AXIS_COUNT)
            pending.push_back(InputEvent::Axis(a.which,GamepadAxisNames.at(a.axis),Normalized(a.axis,a.value)));
    } else if(e.type==SDL_EVENT_GAMEPAD_BUTTON_DOWN || e.type==SDL_EVENT_GAMEPAD_BUTTON_UP) {
        const auto& b=e.gbutton; const auto key=std::make_pair(b.which,int(b.button));
        if(!collect || !active) { if(b.down) suppressed.insert(key); else suppressed.erase(key); return; }
        if(suppressed.contains(key)) { if(!b.down) suppressed.erase(key); return; }
        if(devices.contains(b.which) && b.button<SDL_GAMEPAD_BUTTON_COUNT)
            pending.push_back(InputEvent::GamepadButton(b.which,GamepadButtonNames.at(b.button),b.down));
    }
    if(pending.size()>100000) throw std::runtime_error("Input event queue exceeded 100000 events");
}
}
