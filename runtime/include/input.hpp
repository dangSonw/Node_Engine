#pragma once
#include "values.hpp"
#include <map>
#include <array>
#include <set>
#include <string>
#include <vector>

namespace rt {
struct Ctx;
enum class InputKind { Button, Position, Motion, Wheel, GamepadConnection, GamepadAxis, GamepadButton };
struct InputEvent {
    std::string button; bool down=false; // Empty button releases all.
    InputKind kind=InputKind::Button;
    Vec3 value{0}, delta{0};
    std::int64_t controller=0;
    bool releases_all() const { return kind==InputKind::Button && button.empty(); }
    static InputEvent Position(double x,double y) { return {"",false,InputKind::Position,{x,y,0}}; }
    static InputEvent Motion(double x,double y,double dx,double dy) { return {"",false,InputKind::Motion,{x,y,0},{dx,dy,0}}; }
    static InputEvent Wheel(double x,double y) { return {"",false,InputKind::Wheel,{x,y,0}}; }
    static InputEvent Controller(std::int64_t id,bool connected) { return {"",connected,InputKind::GamepadConnection,{0,0,0},{0,0,0},id}; }
    static InputEvent Axis(std::int64_t id,std::string name,double value) { return {std::move(name),false,InputKind::GamepadAxis,{value,0,0},{0,0,0},id}; }
    static InputEvent GamepadButton(std::int64_t id,std::string name,bool down) { return {std::move(name),down,InputKind::GamepadButton,{0,0,0},{0,0,0},id}; }
};
struct GamepadState { std::array<double,6> axes{}; std::set<std::string> held; };
extern const std::vector<std::string> GamepadAxisNames,GamepadButtonNames;
bool IsGamepadButton(const std::string& name);
bool IsController(std::int64_t id);
struct InputButton {
    std::string button; std::int64_t controller=-1; // -1: keyboard/mouse; 0: any gamepad.
    bool operator==(const InputButton&) const = default;
};
struct GamepadAxisBinding { std::string axis; std::int64_t controller=0; double dead_zone=.15; bool invert=false; };
struct InputAxisBinding { std::vector<InputButton> negative,positive; std::vector<GamepadAxisBinding> gamepads; };
struct InputState {
    Json bindings;
    std::map<std::string,std::vector<InputButton>> actions;
    std::map<std::string,InputAxisBinding> axes;
    std::set<std::string> pressed, released, actions_pressed, actions_released;
    std::map<std::string,bool> contexts;
    std::map<std::string,std::vector<std::string>> action_contexts,axis_contexts;
    std::set<std::string> suppressed_actions;
    Vec3 mouse_position{0}, mouse_delta{0}, mouse_wheel{0};
    bool cursor_visible=true, cursor_locked=false;
    std::string cursor_node;
    std::map<std::int64_t,GamepadState> gamepads;
};
bool IsInputButton(const std::string& button);
void LoadInput(Ctx& c,const Json& bindings);
void AdvanceInput(Ctx& c,const std::vector<InputEvent>& events);
void ClearInput(Ctx& c);
Json InputCheckpoint(const Ctx& c);
void RestoreInputCheckpoint(Ctx& c,const Json& checkpoint);
bool KeyPressed(Ctx& c,const std::string& key);
bool KeyReleased(Ctx& c,const std::string& key);
bool ActionHeld(Ctx& c,const std::string& name);
bool InputActionAvailable(const Ctx& c,const std::string& name);
bool ActionPressed(Ctx& c,const std::string& name);
bool ActionReleased(Ctx& c,const std::string& name);
double InputAxis(Ctx& c,const std::string& name);
bool InputContextEnabled(Ctx& c,const std::string& name);
void SetInputContextEnabled(Ctx& c,const std::string& name,bool enabled);
Vec3 MousePosition(Ctx& c);
Vec3 MouseDelta(Ctx& c);
Vec3 MouseWheel(Ctx& c);
void SetCursorVisible(Ctx& c,bool visible);
void LockCursor(Ctx& c,bool locked);
std::vector<std::int64_t> ConnectedControllers(Ctx& c);
double GamepadAxis(Ctx& c,std::int64_t controller,const std::string& axis,double dead_zone);
std::map<unsigned long long,std::vector<InputEvent>> LoadInputReplay(const Json& replay);
}
