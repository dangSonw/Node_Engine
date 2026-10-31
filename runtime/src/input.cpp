#include "runtime.hpp"

namespace rt {
bool IsController(std::int64_t id) { return id>0 && id<=4294967295LL; }
bool IsGamepadButton(const std::string& name) { return std::find(GamepadButtonNames.begin(),GamepadButtonNames.end(),name)!=GamepadButtonNames.end(); }
namespace {
size_t AxisIndex(const std::string& name) {
    auto it=std::find(GamepadAxisNames.begin(),GamepadAxisNames.end(),name);
    if(it==GamepadAxisNames.end()) throw std::runtime_error("Unknown gamepad axis: "+name);
    return size_t(it-GamepadAxisNames.begin());
}
void AxisValue(size_t axis,double value) {
    if(!std::isfinite(value) || value>1 || value<(axis<4 ? -1 : 0)) throw std::runtime_error("Gamepad axis value outside normalized range");
}
bool GamepadKind(InputKind kind) { return kind==InputKind::GamepadConnection || kind==InputKind::GamepadAxis || kind==InputKind::GamepadButton; }
void ApplyGamepad(std::map<std::int64_t,GamepadState>& pads,const InputEvent& e,Ctx* delivery=nullptr) {
    auto release=[&](std::int64_t id,GamepadState& pad) {
        if(delivery) for(const auto& button:pad.held) QueueInputEvent(*delivery,10020,button,false,id);
        pad.held.clear(); pad.axes.fill(0);
    };
    if(e.releases_all()) { for(auto& [id,pad]:pads) release(id,pad); return; }
    if(!GamepadKind(e.kind)) return;
    if(!IsController(e.controller) || e.delta!=Vec3(0) || e.value.y!=0 || e.value.z!=0)
        throw std::runtime_error("Invalid gamepad input event");
    if(e.kind==InputKind::GamepadConnection) {
        if(!e.button.empty() || e.value!=Vec3(0)) throw std::runtime_error("Invalid gamepad connection event");
        if(e.down) {
            if(!pads.contains(e.controller) && pads.size()>=16) throw std::runtime_error("At most 16 connected gamepads are supported");
            pads.try_emplace(e.controller);
        } else if(auto it=pads.find(e.controller);it!=pads.end()) { release(it->first,it->second); pads.erase(it); }
        return;
    }
    size_t axis=0;
    if(e.kind==InputKind::GamepadAxis) { axis=AxisIndex(e.button); AxisValue(axis,e.value.x); if(e.down) throw std::runtime_error("Invalid gamepad axis event"); }
    else if(!IsGamepadButton(e.button) || e.value!=Vec3(0)) throw std::runtime_error("Invalid gamepad button event");
    auto it=pads.find(e.controller);
    if(it==pads.end()) throw std::runtime_error("Gamepad input requires a connected controller");
    auto& pad=it->second;
    if(e.kind==InputKind::GamepadAxis) pad.axes[axis]=e.value.x;
    else if(pad.held.contains(e.button)!=e.down) {
        if(e.down) pad.held.insert(e.button); else pad.held.erase(e.button);
        if(delivery) QueueInputEvent(*delivery,10020,e.button,e.down,e.controller);
    }
}
Vec3 PointerVector(const Json& value) {
    if(!value.is_array() || value.size()!=2) throw std::runtime_error("Pointer value needs two finite numbers");
    return {FromJson<double>(value.at(0)),FromJson<double>(value.at(1)),0};
}
void Name(const std::string& name) {
    if(name.empty() || name.size()>128 || name.find_first_not_of(' ')==std::string::npos ||
       std::any_of(name.begin(),name.end(),[](unsigned char c){return c<32 || c==127;}))
        throw std::runtime_error("Invalid input binding name");
}
std::int64_t BindingController(const Json& value) {
    auto id=FromJson<std::int64_t>(value);
    if(id!=0 && !IsController(id)) throw std::runtime_error("Binding controller must be 0 (any) or a positive 32-bit ID");
    return id;
}
std::vector<InputButton> Buttons(const Json& value,bool modern,bool empty=false) {
    if(!value.is_array() || (!empty && value.empty()) || value.size()>16) throw std::runtime_error("Invalid input button list size");
    std::vector<InputButton> result;
    for(const auto& v:value) {
        InputButton key;
        if(v.is_string()) {
            key.button=v.get<std::string>();
            if(!IsInputButton(key.button)) throw std::runtime_error("Unknown input button: "+key.button);
        } else if(modern && v.is_object() && v.size()==2) {
            key.button=FromJson<std::string>(v.at("button")); key.controller=BindingController(v.at("controller"));
            if(!IsGamepadButton(key.button)) throw std::runtime_error("Unknown gamepad button: "+key.button);
        } else throw std::runtime_error("Invalid input button binding");
        if(std::find(result.begin(),result.end(),key)!=result.end()) throw std::runtime_error("Duplicate input button binding");
        result.push_back(key);
    }
    return result;
}
bool Held(const Ctx& c,const std::vector<InputButton>& buttons) {
    return std::any_of(buttons.begin(),buttons.end(),[&](const auto& b){
        if(b.controller==-1) return c.keys.contains(b.button);
        for(const auto& [id,pad]:c.input.gamepads) if((b.controller==0 || b.controller==id) && pad.held.contains(b.button)) return true;
        return false;
    });
}
std::map<std::string,bool> ActionState(Ctx& c) {
    std::map<std::string,bool> previous;
    for(const auto& [name,buttons]:c.input.actions) previous[name]=ActionHeld(c,name);
    return previous;
}
void ActionChanges(Ctx& c,const std::map<std::string,bool>& previous) {
    for(const auto& [name,buttons]:c.input.actions) {
        if(!Held(c,buttons)) c.input.suppressed_actions.erase(name);
        bool held=ActionHeld(c,name);
        if(held && !previous.at(name)) c.input.actions_pressed.insert(name);
        if(!held && previous.at(name)) c.input.actions_released.insert(name);
        if(held!=previous.at(name)) QueueInputEvent(c,held ? 10011 : 10012,name,held);
    }
}
void Button(Ctx& c,const std::string& button,bool down) {
    if(c.keys.contains(button)==down) return;
    const auto previous=ActionState(c);
    if(down) { c.keys.insert(button); c.input.pressed.insert(button); }
    else { c.keys.erase(button); c.input.released.insert(button); }
    QueueInputEvent(c,button.starts_with("Mouse") ? 10010 : down ? 10008 : 10009,button,down);
    ActionChanges(c,previous);
}
void Gamepad(Ctx& c,const InputEvent& event) {
    if(event.kind==InputKind::GamepadAxis) { ApplyGamepad(c.input.gamepads,event,&c); return; }
    const auto previous=ActionState(c);
    ApplyGamepad(c.input.gamepads,event,&c); ActionChanges(c,previous);
}
bool Available(const InputState& input,const std::map<std::string,std::vector<std::string>>& memberships,const std::string& name) {
    auto it=memberships.find(name);
    return it==memberships.end() || std::any_of(it->second.begin(),it->second.end(),[&](const auto& context){return input.contexts.at(context);});
}
}
void LoadInput(Ctx& c,const Json& bindings) {
    InputState next;
    if(bindings.is_null()) { c.input=std::move(next); return; }
    if(!bindings.is_object() || !bindings.contains("version") ||
       !bindings.at("version").is_number_integer() || (bindings.at("version")!=1 && bindings.at("version")!=2 && bindings.at("version")!=3) ||
       (bindings.at("version")==3 ? bindings.size()!=4 || !bindings.contains("contexts") : bindings.size()!=3) ||
       !bindings.contains("actions") || !bindings.contains("axes")) throw std::runtime_error("Invalid input bindings/version");
    const bool modern=bindings.at("version")>=2;
    for(const auto* group:{"actions","axes"}) {
        const auto& entries=bindings.at(group);
        if(!entries.is_object() || entries.size()>256) throw std::runtime_error("At most 256 actions/axes are allowed");
        for(const auto& [name,value]:entries.items()) {
            Name(name);
            if(std::string(group)=="actions") next.actions.emplace(name,Buttons(value,modern));
            else {
                if(!value.is_object() || !(value.size()==2 || (modern && value.size()==3 && value.contains("gamepads"))) || !value.contains("negative") || !value.contains("positive"))
                    throw std::runtime_error("Axis needs negative and positive buttons");
                InputAxisBinding axis; axis.negative=Buttons(value.at("negative"),modern,modern); axis.positive=Buttons(value.at("positive"),modern,modern);
                for(const auto& key:axis.negative) if(std::find(axis.positive.begin(),axis.positive.end(),key)!=axis.positive.end())
                    throw std::runtime_error("Axis button bound to both directions");
                if(value.contains("gamepads")) {
                    const auto& pads=value.at("gamepads"); std::set<std::pair<std::int64_t,std::string>> seen;
                    if(!pads.is_array() || pads.empty() || pads.size()>16) throw std::runtime_error("Axis needs 1-16 gamepad bindings");
                    for(const auto& pad:pads) {
                        if(!pad.is_object() || pad.size()!=4) throw std::runtime_error("Invalid gamepad axis binding");
                        GamepadAxisBinding b{FromJson<std::string>(pad.at("axis")),BindingController(pad.at("controller")),
                            FromJson<double>(pad.at("dead_zone")),FromJson<bool>(pad.at("invert"))};
                        AxisIndex(b.axis);
                        if(b.dead_zone<0 || b.dead_zone>=1 || !seen.emplace(b.controller,b.axis).second)
                            throw std::runtime_error("Invalid dead zone or duplicate gamepad axis binding");
                        axis.gamepads.push_back(b);
                    }
                }
                if(axis.negative.empty() && axis.positive.empty() && axis.gamepads.empty()) throw std::runtime_error("Empty axis binding");
                next.axes.emplace(name,std::move(axis));
            }
        }
    }
    if(bindings.at("version")==3) {
        const auto& contexts=bindings.at("contexts");
        if(!contexts.is_object() || contexts.size()>64) throw std::runtime_error("At most 64 input contexts are allowed");
        for(const auto& [name,context]:contexts.items()) {
            Name(name);
            if(!context.is_object() || context.size()!=3) throw std::runtime_error("Invalid input context definition");
            next.contexts[name]=FromJson<bool>(context.at("enabled"));
            size_t count=0;
            for(const auto* group:{"actions","axes"}) {
                const auto& values=context.at(group); std::set<std::string> seen;
                if(!values.is_array() || values.size()>256) throw std::runtime_error("Invalid context membership list");
                const bool actions=std::string(group)=="actions";
                for(const auto& value:values) {
                    auto member=FromJson<std::string>(value);
                    if(!(actions ? next.actions.contains(member) : next.axes.contains(member)) || !seen.insert(member).second)
                        throw std::runtime_error("Unknown or duplicate input context member: "+member);
                    (actions ? next.action_contexts : next.axis_contexts)[member].push_back(name); ++count;
                }
            }
            if(!count) throw std::runtime_error("Input context needs at least one action or axis");
        }
    }
    next.bindings=bindings;
    c.input=std::move(next);
}
void AdvanceInput(Ctx& c,const std::vector<InputEvent>& events) {
    Vec3 position=c.input.mouse_position,delta{0},wheel{0};
    auto pads=c.input.gamepads;
    // Validate the entire batch, including accumulated overflow, before mutation.
    for(const auto& event:events) {
        ApplyGamepad(pads,event);
        if(GamepadKind(event.kind)) continue;
        if(event.controller!=0) throw std::runtime_error("Unexpected controller on keyboard/pointer event");
        if(event.kind==InputKind::Button) {
            if(!event.button.empty() && !IsInputButton(event.button)) throw std::runtime_error("Unknown input button: "+event.button);
            if(event.releases_all()) { delta=Vec3(0); wheel=Vec3(0); }
        } else {
            finite(event.value); finite(event.delta);
            if(!event.button.empty() || event.down || event.value.z!=0 || event.delta.z!=0)
                throw std::runtime_error("Invalid pointer input event");
            if(event.kind==InputKind::Position) { if(!c.input.cursor_locked) position=event.value; }
            else if(event.kind==InputKind::Motion) { if(!c.input.cursor_locked) position=event.value; delta=finite(delta+event.delta); }
            else if(event.kind==InputKind::Wheel) wheel=finite(wheel+event.value);
            else throw std::runtime_error("Unknown pointer input kind");
        }
    }
    c.input.mouse_position=position; c.input.mouse_delta=delta; c.input.mouse_wheel=wheel;
    c.input.pressed.clear(); c.input.released.clear();
    c.input.actions_pressed.clear(); c.input.actions_released.clear();
    for(const auto& event:events) {
        if(GamepadKind(event.kind)) { Gamepad(c,event); continue; }
        if(event.kind!=InputKind::Button) continue;
        if(event.button.empty()) {
            auto held=c.keys;
            for(const auto& key:held) Button(c,key,false);
            Gamepad(c,event);
        } else Button(c,event.button,event.down);
    }
}
void ClearInput(Ctx& c) { c.keys.clear(); c.input.suppressed_actions.clear(); for(auto& [id,pad]:c.input.gamepads) { pad.held.clear(); pad.axes.fill(0); } AdvanceInput(c,{}); ClearInputEvents(c); }
Json InputCheckpoint(const Ctx& c) {
    const auto pair=[](Vec3 v) { return Json::array({v.x,v.y}); };
    Json pads=Json::array();
    for(const auto& [id,pad]:c.input.gamepads) pads.push_back({{"controller",id},{"axes",pad.axes},{"held",pad.held}});
    std::set<std::string> enabled; for(const auto& [name,on]:c.input.contexts) if(on) enabled.insert(name);
    return {{"version",5},{"bindings",c.input.bindings},{"held",c.keys},
        {"pressed",c.input.pressed},{"released",c.input.released},
        {"actions_pressed",c.input.actions_pressed},{"actions_released",c.input.actions_released},
        {"pointer",{{"position",pair(c.input.mouse_position)},{"delta",pair(c.input.mouse_delta)},{"wheel",pair(c.input.mouse_wheel)}}},
        {"cursor",{{"visible",c.input.cursor_visible},{"locked",c.input.cursor_locked},{"node",c.input.cursor_node}}},{"gamepads",std::move(pads)},
        {"enabled_contexts",enabled},{"suppressed_actions",c.input.suppressed_actions}};
}
void RestoreInputCheckpoint(Ctx& c,const Json& checkpoint) {
    if(!checkpoint.is_object() || !checkpoint.contains("version") || !checkpoint.at("version").is_number_integer() ||
       !((checkpoint.at("version")==1 && checkpoint.size()==7) || (checkpoint.at("version")==2 && checkpoint.size()==8) ||
         (checkpoint.at("version")==3 && checkpoint.size()==9) || (checkpoint.at("version")==4 && checkpoint.size()==10) ||
         (checkpoint.at("version")==5 && checkpoint.size()==12)))
        throw std::runtime_error("Invalid input checkpoint/version");
    Ctx next;
    LoadInput(next,checkpoint.at("bindings"));
    auto read=[&](const char* key,bool actions) {
        const auto& values=checkpoint.at(key);
        if(!values.is_array() || values.size()>256) throw std::runtime_error("Invalid input checkpoint set");
        std::set<std::string> result;
        for(const auto& value:values) {
            if(!value.is_string()) throw std::runtime_error("Input checkpoint entries must be text");
            auto name=value.get<std::string>();
            if(!(actions ? next.input.actions.contains(name) : IsInputButton(name)) || !result.insert(name).second)
                throw std::runtime_error("Unknown or duplicate input checkpoint entry: "+name);
        }
        return result;
    };
    next.keys=read("held",false);
    next.input.pressed=read("pressed",false); next.input.released=read("released",false);
    next.input.actions_pressed=read("actions_pressed",true); next.input.actions_released=read("actions_released",true);
    if(checkpoint.at("version")>=2) {
        const auto& pointer=checkpoint.at("pointer");
        if(!pointer.is_object() || pointer.size()!=3) throw std::runtime_error("Invalid input checkpoint pointer");
        next.input.mouse_position=PointerVector(pointer.at("position"));
        next.input.mouse_delta=PointerVector(pointer.at("delta"));
        next.input.mouse_wheel=PointerVector(pointer.at("wheel"));
    }
    if(checkpoint.at("version")>=3) {
        const auto& cursor=checkpoint.at("cursor");
        if(!cursor.is_object() || cursor.size()!=3 || !cursor.at("visible").is_boolean() || !cursor.at("locked").is_boolean())
            throw std::runtime_error("Invalid input checkpoint cursor");
        next.input.cursor_visible=cursor.at("visible").get<bool>();
        next.input.cursor_locked=cursor.at("locked").get<bool>();
        next.input.cursor_node=FromJson<std::string>(cursor.at("node"));
    }
    if(checkpoint.at("version")>=4) {
        const auto& pads=checkpoint.at("gamepads");
        if(!pads.is_array() || pads.size()>16) throw std::runtime_error("Invalid input checkpoint gamepads");
        for(const auto& pad:pads) {
            if(!pad.is_object() || pad.size()!=3) throw std::runtime_error("Invalid checkpoint gamepad");
            auto id=FromJson<std::int64_t>(pad.at("controller"));
            if(!IsController(id) || next.input.gamepads.contains(id)) throw std::runtime_error("Invalid or duplicate checkpoint controller");
            GamepadState state; const auto& axes=pad.at("axes"); const auto& held=pad.at("held");
            if(!axes.is_array() || axes.size()!=6 || !held.is_array() || held.size()>GamepadButtonNames.size()) throw std::runtime_error("Invalid checkpoint gamepad controls");
            for(size_t i=0;i<6;++i) { state.axes[i]=FromJson<double>(axes.at(i)); AxisValue(i,state.axes[i]); }
            for(const auto& b:held) {
                auto name=FromJson<std::string>(b);
                if(!IsGamepadButton(name) || !state.held.insert(name).second) throw std::runtime_error("Invalid checkpoint gamepad button");
            }
            next.input.gamepads.emplace(id,std::move(state));
        }
    }
    if(checkpoint.at("version")==5) {
        const auto& enabled=checkpoint.at("enabled_contexts");
        if(!enabled.is_array() || enabled.size()>64) throw std::runtime_error("Invalid enabled input contexts");
        for(auto& [name,on]:next.input.contexts) on=false;
        for(const auto& v:enabled) {
            auto name=FromJson<std::string>(v); auto it=next.input.contexts.find(name);
            if(it==next.input.contexts.end() || it->second) throw std::runtime_error("Unknown or duplicate enabled input context");
            it->second=true;
        }
        next.input.suppressed_actions=read("suppressed_actions",true);
        for(const auto& name:next.input.suppressed_actions)
            if(!Available(next.input,next.input.action_contexts,name) || !Held(next,next.input.actions.at(name)))
                throw std::runtime_error("Suppressed action must be available with a held alternative");
        for(const auto& name:next.input.actions_pressed)
            if(!Available(next.input,next.input.action_contexts,name) || next.input.suppressed_actions.contains(name))
                throw std::runtime_error("Unavailable action cannot have a pressed edge");
    }
    // A frame may contain both a press and a release, including a second press.
    // Restore the recorded edges directly; replaying them would lose that history.
    c.keys.swap(next.keys); std::swap(c.input,next.input);
}
bool KeyPressed(Ctx& c,const std::string& key) { return c.input.pressed.contains(key); }
bool KeyReleased(Ctx& c,const std::string& key) { return c.input.released.contains(key); }
bool InputActionAvailable(const Ctx& c,const std::string& name) {
    return Available(c.input,c.input.action_contexts,name) && !c.input.suppressed_actions.contains(name);
}
bool ActionHeld(Ctx& c,const std::string& name) {
    auto it=c.input.actions.find(name);
    if(it==c.input.actions.end()) throw std::runtime_error("Unknown input action: "+name);
    return InputActionAvailable(c,name) && Held(c,it->second);
}
bool ActionPressed(Ctx& c,const std::string& name) { ActionHeld(c,name); return c.input.actions_pressed.contains(name); }
bool ActionReleased(Ctx& c,const std::string& name) { ActionHeld(c,name); return c.input.actions_released.contains(name); }
double InputAxis(Ctx& c,const std::string& name) {
    auto it=c.input.axes.find(name);
    if(it==c.input.axes.end()) throw std::runtime_error("Unknown input axis: "+name);
    if(!Available(c.input,c.input.axis_contexts,name)) return 0;
    const auto& axis=it->second;
    double result=double(Held(c,axis.positive))-double(Held(c,axis.negative));
    for(const auto& b:axis.gamepads) {
        double value=0;
        if(b.controller) value=GamepadAxis(c,b.controller,b.axis,b.dead_zone);
        else for(const auto& [id,pad]:c.input.gamepads) {
            const auto candidate=GamepadAxis(c,id,b.axis,b.dead_zone);
            if(std::abs(candidate)>std::abs(value)) value=candidate;
        }
        result+=b.invert ? -value : value;
    }
    return std::clamp(result,-1.0,1.0);
}
bool InputContextEnabled(Ctx& c,const std::string& name) {
    auto it=c.input.contexts.find(name);
    if(it==c.input.contexts.end()) throw std::runtime_error("Unknown input context: "+name);
    return it->second;
}
void SetInputContextEnabled(Ctx& c,const std::string& name,bool enabled) {
    if(InputContextEnabled(c,name)==enabled) return;
    auto previous=ActionState(c); std::map<std::string,bool> available;
    for(const auto& [action,buttons]:c.input.actions) available[action]=Available(c.input,c.input.action_contexts,action);
    c.input.contexts.at(name)=enabled; std::set<std::string> changed;
    for(const auto& [action,buttons]:c.input.actions) {
        if(available.at(action)==Available(c.input,c.input.action_contexts,action)) continue;
        changed.insert(action); c.input.suppressed_actions.erase(action);
        c.input.actions_pressed.erase(action); c.input.actions_released.erase(action);
        if(enabled && Held(c,buttons)) c.input.suppressed_actions.insert(action);
    }
    ClearInputActionEvents(c,changed);
    for(const auto& action:changed) if(previous.at(action) && !ActionHeld(c,action)) {
        c.input.actions_released.insert(action); QueueInputEvent(c,10012,action,false);
    }
}
std::map<unsigned long long,std::vector<InputEvent>> LoadInputReplay(const Json& replay) {
    if(!replay.is_object() || replay.size()!=2 || !replay.contains("version") ||
       !replay.at("version").is_number_integer() || (replay.at("version")!=1 && replay.at("version")!=2 && replay.at("version")!=3) ||
       !replay.contains("events") || !replay.at("events").is_array() || replay.at("events").size()>100000)
        throw std::runtime_error("Invalid input replay/version");
    std::map<unsigned long long,std::vector<InputEvent>> result;
    unsigned long long previous=0;
    for(const auto& e:replay.at("events")) {
        if(!e.is_object() || !e.contains("frame") || !e.at("frame").is_number_unsigned() || e.at("frame")>=1000000)
            throw std::runtime_error("Replay frame must be an integer from 0 to 999999");
        auto frame=e.at("frame").get<unsigned long long>();
        if(frame<previous) throw std::runtime_error("Replay events must be ordered by frame");
        previous=frame;
        if(e.size()==2 && e.contains("release_all") && e.at("release_all").is_boolean() && e.at("release_all")==true)
            result[frame].push_back({});
        else if(e.size()==3 && e.contains("button") && e.at("button").is_string() &&
                e.contains("down") && e.at("down").is_boolean() && IsInputButton(e.at("button").get<std::string>()))
            result[frame].push_back({e.at("button").get<std::string>(),e.at("down").get<bool>()});
        else if(replay.at("version")==3 && e.contains("controller")) {
            const auto id=FromJson<std::int64_t>(e.at("controller"));
            if(!IsController(id)) throw std::runtime_error("Invalid replay controller");
            const auto type=e.at("type").get<std::string>();
            if(type=="gamepad_connection" && e.size()==4 && e.at("connected").is_boolean())
                result[frame].push_back(InputEvent::Controller(id,e.at("connected").get<bool>()));
            else if(type=="gamepad_axis" && e.size()==5) {
                auto axis=e.at("axis").get<std::string>(); auto value=FromJson<double>(e.at("value")); AxisValue(AxisIndex(axis),value);
                result[frame].push_back(InputEvent::Axis(id,std::move(axis),value));
            } else if(type=="gamepad_button" && e.size()==5 && e.at("down").is_boolean() && IsGamepadButton(e.at("button").get<std::string>()))
                result[frame].push_back(InputEvent::GamepadButton(id,e.at("button").get<std::string>(),e.at("down").get<bool>()));
            else throw std::runtime_error("Invalid gamepad replay event");
        }
        else if(replay.at("version")>=2 && e.contains("type") && e.at("type").is_string()) {
            const auto type=e.at("type").get<std::string>();
            if((type=="position" || type=="wheel") && e.size()==4) {
                const auto x=FromJson<double>(e.at("x")),y=FromJson<double>(e.at("y"));
                result[frame].push_back(type=="position" ? InputEvent::Position(x,y) : InputEvent::Wheel(x,y));
            } else if(type=="motion" && e.size()==6) {
                result[frame].push_back(InputEvent::Motion(FromJson<double>(e.at("x")),FromJson<double>(e.at("y")),
                    FromJson<double>(e.at("dx")),FromJson<double>(e.at("dy"))));
            } else throw std::runtime_error("Invalid pointer replay event");
        } else throw std::runtime_error("Replay event needs a supported button/down, release_all:true or version-2 pointer event");
    }
    return result;
}
Vec3 MousePosition(Ctx& c) { return c.input.mouse_position; }
Vec3 MouseDelta(Ctx& c) { return c.input.mouse_delta; }
Vec3 MouseWheel(Ctx& c) { return c.input.mouse_wheel; }
void SetCursorVisible(Ctx& c,bool visible) { c.input.cursor_visible=visible; c.input.cursor_node=c.current_node; }
void LockCursor(Ctx& c,bool locked) { c.input.cursor_locked=locked; c.input.cursor_node=c.current_node; }
std::vector<std::int64_t> ConnectedControllers(Ctx& c) {
    std::vector<std::int64_t> result; for(const auto& [id,pad]:c.input.gamepads) result.push_back(id); return result;
}
double GamepadAxis(Ctx& c,std::int64_t controller,const std::string& axis,double dead_zone) {
    const auto index=AxisIndex(axis);
    if((controller!=0 && !IsController(controller)) || !std::isfinite(dead_zone) || dead_zone<0 || dead_zone>=1)
        throw std::runtime_error("Gamepad controller must be 0..4294967295 and dead zone in [0,1)");
    auto pad=controller==0 ? c.input.gamepads.begin() : c.input.gamepads.find(controller);
    if(pad==c.input.gamepads.end()) return 0;
    const auto value=pad->second.axes[index];
    return std::abs(value)<=dead_zone ? 0 : std::copysign((std::abs(value)-dead_zone)/(1-dead_zone),value);
}
}
