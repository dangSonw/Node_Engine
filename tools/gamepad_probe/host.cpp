// Test executable only: the production SDL host with an actual virtual controller.
#define SDL_MAIN_HANDLED 1
#define SDL_AppInit EngineAppInit
#define SDL_AppIterate EngineAppIterate
#define SDL_AppEvent EngineAppEvent
#define SDL_AppQuit EngineAppQuit
#include "../../runtime/src/app.cpp"
#undef SDL_AppInit
#undef SDL_AppIterate
#undef SDL_AppEvent
#undef SDL_AppQuit
#undef main
namespace {
SDL_JoystickID controller=0;
SDL_Joystick* joystick=nullptr;
void Disconnect() {
    if(joystick) { SDL_CloseJoystick(joystick); joystick=nullptr; }
    if(controller) { SDL_DetachVirtualJoystick(controller); controller=0; }
}
void Control(App& a,const rt::Json& m) {
    const auto operation=m.at("operation").get<std::string>(); bool okay=true;
    if(operation=="connect") {
        if(controller) throw std::runtime_error("Probe controller already connected");
        SDL_VirtualJoystickDesc desc{}; SDL_INIT_INTERFACE(&desc);
        desc.type=SDL_JOYSTICK_TYPE_GAMEPAD; desc.naxes=6; desc.nbuttons=SDL_GAMEPAD_BUTTON_COUNT;
        desc.axis_mask=63; desc.button_mask=(1u<<SDL_GAMEPAD_BUTTON_COUNT)-1; desc.name="Node Engine editor acceptance gamepad";
        controller=SDL_AttachVirtualJoystick(&desc); joystick=SDL_OpenJoystick(controller); okay=controller && joystick;
    } else if(operation=="disconnect") Disconnect();
    else if(!joystick) throw std::runtime_error("Probe controller is disconnected");
    else if(operation=="axis") okay=SDL_SetJoystickVirtualAxis(joystick,m.at("axis").get<int>(),m.at("value").get<Sint16>());
    else if(operation=="button") okay=SDL_SetJoystickVirtualButton(joystick,m.at("button").get<int>(),m.at("down").get<bool>());
    else throw std::runtime_error("Unknown probe operation");
    if(!okay) throw std::runtime_error(SDL_GetError());
    SDL_UpdateJoysticks();
    a.event({{"event","probe_gamepad"},{"controller",controller},{"operation",operation}});
    a.event({{"event","ack"},{"id",m.value("id",0)},{"command","probe_gamepad"}});
}
SDL_AppResult Iterate(void* state) {
    auto& a=*static_cast<App*>(state);
    if(a.channel) for(const auto& m:a.channel->receive()) {
        try { if(m.value("command","")=="probe_gamepad") Control(a,m); else a.command(m); }
        catch(const std::exception& e) { a.event({{"event","node_error"},{"node",a.ctx.current_node},{"message",e.what()},{"id",m.value("id",0)}}); }
    }
    return EngineAppIterate(state);
}
void Quit(void* state,SDL_AppResult result) { Disconnect(); EngineAppQuit(state,result); }
}
int main(int argc,char** argv) { SDL_SetMainReady(); return SDL_EnterAppMainCallbacks(argc,argv,EngineAppInit,Iterate,EngineAppEvent,Quit); }
