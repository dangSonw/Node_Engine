#pragma once
#include "input.hpp"
#include <SDL3/SDL.h>

namespace rt {
class GamepadDevices {
    std::map<SDL_JoystickID,SDL_Gamepad*> devices;
    std::set<std::pair<SDL_JoystickID,int>> suppressed;
    bool active=false;
    void open(SDL_JoystickID);
    void close(SDL_JoystickID);
    void sample(std::vector<InputEvent>&,SDL_JoystickID only=0);
public:
    GamepadDevices();
    ~GamepadDevices();
    GamepadDevices(const GamepadDevices&)=delete;
    GamepadDevices& operator=(const GamepadDevices&)=delete;
    void reset(Ctx&,bool focused);
    void sync(bool enabled,std::vector<InputEvent>&);
    void event(const SDL_Event&,bool collect,std::vector<InputEvent>&);
};
}
