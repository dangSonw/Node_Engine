#include "runtime.hpp"
#include "input_devices.hpp"
#include <fstream>
#include <iostream>
using namespace rt;
namespace {
Json checks=Json::array();
void Check(std::string name,bool okay) { if(!okay) throw std::runtime_error(name); checks.push_back(name); }
template<class F> bool Fails(F f) { try { f(); return false; } catch(const std::exception&) { return true; } }
Ctx Initial() {
    Ctx c; LoadScene(c,{{"version",1},{"entities",Json::array()},{"variables",Json::object()}});
    BindInputEvent(c,10020,"pad","",[](Ctx& c,EntityRef,EntityRef,const std::vector<Value>& args) {
        Print(c,std::get<std::string>(args[0])+":"+(std::get<bool>(args[1])?"down":"up")+":"+std::to_string(std::get<std::int64_t>(args[2])));
    }); return c;
}
void Core() {
    auto c=Initial();
    Check("No controller reads neutral",ConnectedControllers(c).empty() && GamepadAxis(c,0,"LeftX",.15)==0);
    AdvanceInput(c,{InputEvent::Controller(7,true),InputEvent::Controller(2,true),InputEvent::Axis(2,"LeftX",-.6),
        InputEvent::Axis(2,"RightTrigger",.6),InputEvent::GamepadButton(7,"South",true),InputEvent::GamepadButton(7,"South",true),
        InputEvent::GamepadButton(7,"South",false),InputEvent::GamepadButton(2,"East",true)});
    Check("Connected IDs sorted and auto controller selects lowest",ConnectedControllers(c)==Array<std::int64_t>{2,7} && std::abs(GamepadAxis(c,0,"LeftX",.2)+.5)<1e-12);
    Check("Trigger and stick dead zones rescale signed values",std::abs(GamepadAxis(c,2,"RightTrigger",.2)-.5)<1e-12 && GamepadAxis(c,2,"LeftX",.7)==0);
    auto input=InputCheckpoint(c),events=EventCheckpoint(c); auto restored=Initial(); RestoreInputCheckpoint(restored,input); RestoreEventCheckpoint(restored,c,events);
    Check("Input and queued controller payload restore exactly",InputCheckpoint(restored)==input && EventCheckpoint(restored)==events);
    for(int i=0;i<4;++i) {
        auto bad=events;
        if(i==0) bad["queue"][0]["args"][2]=0;
        if(i==1) bad["queue"][0]["args"][2]=4294967296LL;
        if(i==2) bad["queue"][0]["args"][2]=true;
        if(i==3) bad["queue"][0]["args"].erase(2);
        Check("Malformed queued controller identity rejects atomically "+std::to_string(i),
            Fails([&]{RestoreEventCheckpoint(restored,c,bad);}) && EventCheckpoint(restored)==events && InputCheckpoint(restored)==input);
    }
    DrainEvents(c); DrainEvents(restored);
    Check("Duplicate downs suppressed and captured edges keep order",c.logs==std::vector<std::string>{"South:down:7","South:up:7","East:down:2"} && restored.logs==c.logs);
    AdvanceInput(c,{InputEvent::Controller(2,false)}); DrainEvents(c);
    Check("Disconnect releases held buttons and removes axes",c.logs.back()=="East:up:2" && GamepadAxis(c,2,"LeftX",0)==0 && ConnectedControllers(c)==Array<std::int64_t>{7});
    AdvanceInput(c,{InputEvent::Controller(2,true)}); Check("Reconnected controller is neutral",GamepadAxis(c,2,"LeftX",0)==0 && c.input.gamepads.at(2).held.empty());
    AdvanceInput(c,{InputEvent::Axis(7,"LeftX",1),InputEvent::GamepadButton(7,"South",true),{},InputEvent::Axis(7,"LeftY",-.5)}); DrainEvents(c);
    Check("Release all clears analog and held state in original order",GamepadAxis(c,7,"LeftX",0)==0 && GamepadAxis(c,7,"LeftY",0)==-.5 && c.input.gamepads.at(7).held.empty());
    auto before=InputCheckpoint(c),queued=EventCheckpoint(c);
    for(auto e:std::vector<InputEvent>{InputEvent::Controller(0,true),InputEvent::Controller(4294967296LL,true),InputEvent::Axis(7,"Bad",0),
        InputEvent::Axis(7,"LeftX",1.01),InputEvent::Axis(7,"LeftTrigger",-.1),InputEvent::Axis(7,"LeftX",NAN),
        InputEvent::Axis(99,"LeftX",0),InputEvent::GamepadButton(7,"A",true),InputEvent::GamepadButton(99,"South",true)})
        Check("Invalid raw gamepad batch rejects atomically "+std::to_string(checks.size()),Fails([&]{AdvanceInput(c,{InputEvent::Axis(7,"LeftX",.5),e});}) && InputCheckpoint(c)==before && EventCheckpoint(c)==queued);
    for(int i=0;i<10;++i) {
        auto bad=before; auto& pad=bad["gamepads"][0];
        if(i==0) pad["controller"]=0; if(i==1) pad["controller"]=true; if(i==2) pad["axes"][0]=2;
        if(i==3) pad["axes"][4]=-.1; if(i==4) pad["axes"][0]=true; if(i==5) pad["held"]={"A"};
        if(i==6) pad["held"]={"South","South"}; if(i==7) pad["extra"]=1;
        if(i==8) bad["gamepads"].push_back(pad); if(i==9) bad.erase("gamepads");
        Check("Malformed gamepad checkpoint rollback "+std::to_string(i),Fails([&]{RestoreInputCheckpoint(c,bad);}) && InputCheckpoint(c)==before);
    }
    auto legacy=before; legacy["version"]=3; legacy.erase("gamepads"); legacy.erase("enabled_contexts"); legacy.erase("suppressed_actions"); RestoreInputCheckpoint(c,legacy);
    Check("Version three input upgrades without inventing devices",ConnectedControllers(c).empty() && InputCheckpoint(c)["cursor"]==legacy["cursor"]);
    for(int i=0;i<16;++i) AdvanceInput(c,{InputEvent::Controller(i+1,true)});
    before=InputCheckpoint(c); Check("Device bound rejects seventeenth controller atomically",Fails([&]{AdvanceInput(c,{InputEvent::Controller(17,true)});}) && InputCheckpoint(c)==before);
    for(double d:{-1.0,1.0,double(NAN)}) Check("Invalid dead zone rejected "+std::to_string(checks.size()),Fails([&]{GamepadAxis(c,1,"LeftX",d);}));
    Check("Invalid controller query rejected",Fails([&]{GamepadAxis(c,-1,"LeftX",0);}) && Fails([&]{GamepadAxis(c,4294967296LL,"LeftX",0);}));
    AdvanceInput(c,{InputEvent::GamepadButton(1,"South",true),InputEvent::Axis(1,"LeftX",1)}); ClearInput(c);
    Check("Pause clears controls and callbacks but retains inventory",ConnectedControllers(c).size()==16 && GamepadAxis(c,1,"LeftX",0)==0 && c.input.gamepads.at(1).held.empty() && EventCheckpoint(c)["queue"].empty());
}
void VirtualDevice() {
    GamepadDevices host; auto c=Initial(); std::vector<InputEvent> pending;
    host.reset(c,true);
    SDL_VirtualJoystickDesc desc{}; SDL_INIT_INTERFACE(&desc); desc.type=SDL_JOYSTICK_TYPE_GAMEPAD; desc.naxes=6; desc.nbuttons=SDL_GAMEPAD_BUTTON_COUNT;
    desc.axis_mask=63; desc.button_mask=(1u<<SDL_GAMEPAD_BUTTON_COUNT)-1; desc.name="Node Engine virtual acceptance controller";
    auto id=SDL_AttachVirtualJoystick(&desc); Check("SDL creates an actual virtual gamepad",id && SDL_IsGamepad(id));
    auto joy=SDL_OpenJoystick(id); if(!joy) throw std::runtime_error(SDL_GetError());
    auto pump=[&] { SDL_UpdateJoysticks(); SDL_Event e; while(SDL_PollEvent(&e)) host.event(e,true,pending); AdvanceInput(c,pending); pending.clear(); DrainEvents(c); };
    pump(); Check("SDL hotplug reaches shared input inventory",c.input.gamepads.contains(id));
    SDL_SetJoystickVirtualAxis(joy,0,-32768); SDL_SetJoystickVirtualAxis(joy,4,32767); pump();
    Check("SDL axes normalize both stick and trigger",GamepadAxis(c,id,"LeftX",0)==-1 && GamepadAxis(c,id,"LeftTrigger",0)==1);
    SDL_SetJoystickVirtualButton(joy,0,true); pump(); Check("SDL gamepad button enters native event delivery",c.logs.back()=="South:down:"+std::to_string(id));
    host.sync(false,pending); pump(); Check("Focus release clears analog and emits held release",GamepadAxis(c,id,"LeftX",0)==0 && c.logs.back()=="South:up:"+std::to_string(id));
    auto size=c.logs.size(); AdvanceInput(c,{{"MouseLeft",true}}); host.sync(true,pending); pump();
    Check("Gamepad focus return preserves the focusing mouse press",c.keys.contains("MouseLeft"));
    Check("Refocus resamples analog without synthetic held button",GamepadAxis(c,id,"LeftX",0)==-1 && c.logs.size()==size);
    SDL_SetJoystickVirtualButton(joy,0,false); pump(); Check("Suppressed held button release stays neutral",c.logs.size()==size);
    SDL_SetJoystickVirtualButton(joy,0,true); pump(); Check("New press rearms after focus return",c.logs.size()==size+1);
    auto second=SDL_AttachVirtualJoystick(&desc); auto second_joy=SDL_OpenJoystick(second);
    Check("A second SDL controller opens independently",second && second_joy); pump();
    SDL_SetJoystickVirtualButton(second_joy,1,true); pump();
    SDL_Event remap{}; remap.type=SDL_EVENT_GAMEPAD_REMAPPED; remap.gdevice.which=id; SDL_PushEvent(&remap); pump();
    Check("Remapping releases only the affected controller",c.input.gamepads.at(id).held.empty() && c.input.gamepads.at(second).held.contains("East"));
    SDL_SetJoystickVirtualButton(second_joy,1,false); pump();
    Check("Other controller release is not suppressed by remap",c.logs.back()=="East:up:"+std::to_string(second));
    SDL_CloseJoystick(second_joy); SDL_DetachVirtualJoystick(second); pump();
    host.reset(c,true); size=c.logs.size(); pump(); Check("Physical Load reset neutralizes held buttons",c.input.gamepads.at(id).held.empty() && c.logs.size()==size);
    SDL_SetJoystickVirtualButton(joy,0,false); pump(); SDL_SetJoystickVirtualButton(joy,0,true); pump();
    SDL_CloseJoystick(joy); SDL_DetachVirtualJoystick(id); pump();
    Check("SDL unplug releases held button and removes the device",!c.input.gamepads.contains(id) && c.logs.back()=="South:up:"+std::to_string(id));
}
Json MappedBindings() {
    const auto button=[](std::string name,std::int64_t id=0){return Json{{"button",name},{"controller",id}};};
    const auto analog=[](std::string axis,std::int64_t id,double dead,bool invert){return Json{{"axis",axis},{"controller",id},{"dead_zone",dead},{"invert",invert}};};
    return {{"version",2},{"actions",{{"jump",Json::array({"Space",button("South")})},{"specific",Json::array({button("East",7)})}}},
        {"axes",{{"horizontal",{{"negative",{"A"}},{"positive",{"D"}},{"gamepads",Json::array({analog("LeftX",0,.2,false)})}}},
                 {"trigger",{{"negative",Json::array()},{"positive",Json::array()},{"gamepads",Json::array({analog("RightTrigger",7,0,true)})}}},
                 {"dpad",{{"negative",Json::array({button("DpadLeft")})},{"positive",Json::array({button("DpadRight")})}}}}}};
}
Ctx Mapped() {
    auto c=Initial(); LoadInput(c,MappedBindings());
    for(bool down:{false,true}) BindInputEvent(c,down?10011:10012,down?"mapped-down":"mapped-up","",[down](Ctx& c,EntityRef,EntityRef,const std::vector<Value>& args){Print(c,std::get<std::string>(args[0])+(down?"+":"-"));});
    return c;
}
void Mappings() {
    auto c=Mapped();
    AdvanceInput(c,{InputEvent::Controller(7,true),InputEvent::Controller(9,true),InputEvent::Axis(7,"LeftX",.6),InputEvent::Axis(9,"LeftX",-.9)});
    Check("Any-controller binding takes greatest magnitude without summing devices",std::abs(InputAxis(c,"horizontal")+.875)<1e-12);
    AdvanceInput(c,{InputEvent::Axis(9,"LeftX",-.6)});
    Check("Equal analog magnitudes choose lowest connection ID",std::abs(InputAxis(c,"horizontal")-.5)<1e-12);
    AdvanceInput(c,{{"D",true}}); Check("Digital plus analog saturates at one",InputAxis(c,"horizontal")==1);
    AdvanceInput(c,{{"A",true}}); Check("Opposing keys leave analog contribution",std::abs(InputAxis(c,"horizontal")-.5)<1e-12);
    AdvanceInput(c,{InputEvent::Axis(7,"RightTrigger",.8),InputEvent::Axis(9,"RightTrigger",1)});
    Check("Explicit controller trigger binding supports inversion",InputAxis(c,"trigger")==-.8);
    AdvanceInput(c,{InputEvent::GamepadButton(7,"DpadLeft",true),InputEvent::GamepadButton(9,"DpadRight",true)});
    Check("Mapped D-pad directions cancel across controllers",InputAxis(c,"dpad")==0);
    AdvanceInput(c,{InputEvent::GamepadButton(9,"DpadRight",false)}); Check("D-pad release preserves other held direction",InputAxis(c,"dpad")==-1);
    DrainEvents(c); c.logs.clear();
    AdvanceInput(c,{{"Space",true},InputEvent::GamepadButton(7,"South",true),{"Space",false},InputEvent::GamepadButton(9,"South",true),InputEvent::GamepadButton(7,"South",false)});
    DrainEvents(c);
    Check("Keyboard to two-controller handoff produces only one action press",ActionHeld(c,"jump") && ActionPressed(c,"jump") && !ActionReleased(c,"jump") &&
        c.logs==std::vector<std::string>{"jump+","South:down:7","South:down:9","South:up:7"});
    c.logs.clear(); AdvanceInput(c,{InputEvent::Controller(9,false)}); DrainEvents(c);
    Check("Last held controller unplug emits raw release before mapped release",!ActionHeld(c,"jump") && ActionReleased(c,"jump") && c.logs==std::vector<std::string>{"South:up:9","jump-"});
    AdvanceInput(c,{InputEvent::Controller(9,true),InputEvent::GamepadButton(9,"East",true)});
    Check("Explicit action controller ignores other devices",!ActionHeld(c,"specific"));
    AdvanceInput(c,{InputEvent::GamepadButton(7,"East",true)}); Check("Explicit action controller accepts matching ID",ActionHeld(c,"specific"));
    DrainEvents(c); c.logs.clear();
    AdvanceInput(c,{InputEvent::GamepadButton(7,"South",true),InputEvent::GamepadButton(7,"South",true),InputEvent::GamepadButton(7,"South",false),InputEvent::GamepadButton(7,"South",true)});
    auto saved=InputCheckpoint(c),events=EventCheckpoint(c); auto restored=Mapped(); RestoreInputCheckpoint(restored,saved); RestoreEventCheckpoint(restored,c,events);
    Check("Mapped bindings, polling edges and queued callbacks checkpoint exactly",InputCheckpoint(restored)==saved && EventCheckpoint(restored)==events && ActionHeld(restored,"jump") && ActionPressed(restored,"jump") && ActionReleased(restored,"jump"));
    DrainEvents(c); DrainEvents(restored);
    Check("Ordered raw and mapped transitions replay once after restore",c.logs==restored.logs && c.logs==std::vector<std::string>{"South:down:7","jump+","South:up:7","jump-","South:down:7","jump+"});
    AdvanceInput(c,{InputEvent::Controller(7,false)}); Check("Missing explicit device reads neutral",InputAxis(c,"trigger")==0 && !ActionHeld(c,"specific"));
    AdvanceInput(c,{{}}); Check("Release-all clears mapped axes/buttons while retaining devices",InputAxis(c,"horizontal")==0 && !ActionHeld(c,"jump") && ConnectedControllers(c)==Array<std::int64_t>{9});
    auto before=InputCheckpoint(c),queued=EventCheckpoint(c); std::vector<Json> bads;
    for(Json value:std::vector<Json>{-1,4294967296LL,true,1.5,"7"}) { auto bad=MappedBindings(); bad["actions"]["jump"][1]["controller"]=value; bads.push_back(bad); }
    for(Json value:std::vector<Json>{"A",1,nullptr}) { auto bad=MappedBindings(); bad["actions"]["jump"][1]["button"]=value; bads.push_back(bad); }
    for(Json value:std::vector<Json>{-.1,1,true,"0.2",nullptr}) { auto bad=MappedBindings(); bad["axes"]["horizontal"]["gamepads"][0]["dead_zone"]=value; bads.push_back(bad); }
    for(int i=0;i<9;++i) {
        auto bad=MappedBindings();
        if(i==0) bad["version"]=1;
        if(i==1) bad["actions"]["jump"].push_back(bad["actions"]["jump"][1]);
        if(i==2) bad["axes"]["horizontal"]["gamepads"].push_back(bad["axes"]["horizontal"]["gamepads"][0]);
        if(i==3) bad["axes"]["trigger"].erase("gamepads");
        if(i==4) bad["axes"]["horizontal"]["gamepads"][0]["invert"]=1;
        if(i==5) bad["axes"]["horizontal"]["gamepads"][0]["axis"]="Bad";
        if(i==6) bad["axes"]["horizontal"]["gamepads"][0]["controller"]=true;
        if(i==7) bad["axes"]["dpad"]["negative"]=bad["axes"]["dpad"]["positive"];
        if(i==8) bad["actions"]["jump"][1]["extra"]=true;
        bads.push_back(bad);
    }
    for(size_t i=0;i<bads.size();++i) {
        const auto& bad=bads[i]; auto checkpoint=before; checkpoint["bindings"]=bad;
        Check("Malformed mixed binding rejects atomically "+std::to_string(i),Fails([&]{LoadInput(c,bad);}) &&
            Fails([&]{RestoreInputCheckpoint(c,checkpoint);}) && InputCheckpoint(c)==before && EventCheckpoint(c)==queued);
    }
    ClearInput(restored); Check("Pause clears mapped edges and callbacks without action releases",!ActionHeld(restored,"jump") && !ActionPressed(restored,"jump") && !ActionReleased(restored,"jump") && EventCheckpoint(restored)["queue"].empty());
}
Json ContextBindings() {
    auto b=MappedBindings(); b["version"]=3;
    b["contexts"]={{"gameplay",{{"enabled",true},{"actions",{"jump"}},{"axes",{"horizontal"}}}},
        {"overlay",{{"enabled",false},{"actions",{"jump"}},{"axes",Json::array()}}}};
    return b;
}
Ctx Contexts() { auto c=Mapped(); LoadInput(c,ContextBindings()); return c; }
void ContextChecks() {
    auto c=Contexts(); Check("Contexts load authored initial enabled state",InputContextEnabled(c,"gameplay") && !InputContextEnabled(c,"overlay"));
    AdvanceInput(c,{{"D",true},{"Space",true},InputEvent::Controller(7,true),InputEvent::Axis(7,"LeftX",1)}); DrainEvents(c); c.logs.clear();
    SetInputContextEnabled(c,"overlay",true); SetInputContextEnabled(c,"gameplay",false); DrainEvents(c);
    Check("Any enabled membership keeps action available while its axis is disabled",ActionHeld(c,"jump") && InputAxis(c,"horizontal")==0 && c.logs.empty());
    SetInputContextEnabled(c,"overlay",false); DrainEvents(c);
    Check("Disabling last context releases the action exactly once",!ActionHeld(c,"jump") && !ActionPressed(c,"jump") && ActionReleased(c,"jump") && c.logs==std::vector<std::string>{"jump-"});
    Check("Context gating leaves raw keys and axes available",c.keys.contains("Space") && GamepadAxis(c,7,"LeftX",0)==1);
    SetInputContextEnabled(c,"gameplay",true); DrainEvents(c);
    Check("Reenable resumes axes but suppresses already held action",InputAxis(c,"horizontal")==1 && !ActionHeld(c,"jump") && !ActionPressed(c,"jump") && !ActionReleased(c,"jump"));
    auto saved=InputCheckpoint(c),events=EventCheckpoint(c); auto restored=Contexts(); RestoreInputCheckpoint(restored,saved); RestoreEventCheckpoint(restored,c,events);
    Check("Enabled contexts and held-action suppression checkpoint exactly",InputCheckpoint(restored)==saved && !ActionHeld(restored,"jump") && InputContextEnabled(restored,"gameplay"));
    for(auto* target:{&c,&restored}) {
        AdvanceInput(*target,{InputEvent::GamepadButton(7,"South",true),{"Space",false}});
        Check("Suppression lasts until every alternative is released",!ActionHeld(*target,"jump") && !ActionPressed(*target,"jump"));
        AdvanceInput(*target,{InputEvent::GamepadButton(7,"South",false)});
        Check("Neutral rearm does not emit a phantom mapped release",target->input.suppressed_actions.empty() && !ActionReleased(*target,"jump"));
        AdvanceInput(*target,{InputEvent::GamepadButton(7,"South",true)});
        Check("New press after rearm reaches the action",ActionHeld(*target,"jump") && ActionPressed(*target,"jump"));
    }
    Check("Restored context continuation matches uninterrupted input and queue",InputCheckpoint(c)==InputCheckpoint(restored) && EventCheckpoint(c)==EventCheckpoint(restored));
    auto press_events=EventCheckpoint(c); SetInputContextEnabled(c,"gameplay",false);
    auto disabled=InputCheckpoint(c),release_events=EventCheckpoint(c); auto loaded=Contexts(); RestoreInputCheckpoint(loaded,disabled); RestoreEventCheckpoint(loaded,c,release_events);
    Check("Disabled context preserves queued final releases across restoration",InputCheckpoint(loaded)==disabled && EventCheckpoint(loaded)==release_events);
    Check("Forged queued press for disabled context rejects atomically",Fails([&]{RestoreEventCheckpoint(loaded,c,press_events);}) && EventCheckpoint(loaded)==release_events);
    for(int i=0;i<8;++i) {
        auto bad=saved;
        if(i==0) bad["enabled_contexts"]={"missing"};
        if(i==1) bad["enabled_contexts"]={"gameplay","gameplay"};
        if(i==2) bad["enabled_contexts"]={1};
        if(i==3) bad["suppressed_actions"]={"missing"};
        if(i==4) bad["suppressed_actions"]={"jump","jump"};
        if(i==5) bad["enabled_contexts"]=Json::array();
        if(i==6) bad["held"]=Json::array();
        if(i==7) bad["actions_pressed"]={"jump"};
        Check("Invalid context checkpoint rollback "+std::to_string(i),Fails([&]{RestoreInputCheckpoint(loaded,bad);}) && InputCheckpoint(loaded)==disabled);
    }
    Check("Unknown context operations reject without mutation",Fails([&]{SetInputContextEnabled(loaded,"missing",true);}) && Fails([&]{InputContextEnabled(loaded,"missing");}) && InputCheckpoint(loaded)==disabled && EventCheckpoint(loaded)==release_events);
    auto replay=Contexts();
    BindInputEvent(replay,10011,"a_toggle","jump",[](Ctx& c,EntityRef,EntityRef,const std::vector<Value>&){Print(c,"toggle"); SetInputContextEnabled(c,"gameplay",false); SetInputContextEnabled(c,"gameplay",true);});
    AdvanceInput(replay,{{"Space",true},InputEvent::Controller(7,true),InputEvent::GamepadButton(7,"East",true)}); DrainEvents(replay);
    Check("Disable/re-enable inside a callback cancels remaining listeners only for that action",replay.logs==std::vector<std::string>{"toggle","East:down:7","specific+"} && !ActionHeld(replay,"jump") && ActionHeld(replay,"specific"));
    auto queued=Contexts();
    BindInputEvent(queued,10008,"menu","M",[](Ctx& c,EntityRef,EntityRef,const std::vector<Value>&){SetInputContextEnabled(c,"gameplay",false);});
    AdvanceInput(queued,{{"M",true},{"Space",true}}); DrainEvents(queued);
    Check("Earlier raw menu callback cancels pending gameplay press and emits cleanup release",queued.logs==std::vector<std::string>{"jump-"} && !ActionHeld(queued,"jump"));
    for(int i=0;i<12;++i) {
        auto bad=ContextBindings(); auto& context=bad["contexts"]["gameplay"];
        if(i==0) context["enabled"]=1;
        if(i==1) context["actions"]={"missing"};
        if(i==2) context["actions"]={"jump","jump"};
        if(i==3) context["axes"]={"missing"};
        if(i==4) context["axes"]={"horizontal","horizontal"};
        if(i==5) context["actions"]=Json::array(),context["axes"]=Json::array();
        if(i==6) context["extra"]=true;
        if(i==7) bad["contexts"][""]=context;
        if(i==8) bad.erase("contexts");
        if(i==9) bad["version"]=2;
        if(i==10) bad["contexts"]=Json::array();
        if(i==11) for(int j=0;j<65;++j) bad["contexts"][std::to_string(j)]=context;
        Check("Malformed context definition rejects atomically "+std::to_string(i),Fails([&]{LoadInput(loaded,bad);}) && InputCheckpoint(loaded)==disabled);
    }
    ClearInput(loaded); Check("Pause keeps disabled contexts but clears controls and pending releases",!InputContextEnabled(loaded,"gameplay") && !ActionHeld(loaded,"jump") && loaded.input.suppressed_actions.empty() && EventCheckpoint(loaded)["queue"].empty());
    auto legacy=InputCheckpoint(Mapped()); legacy["version"]=4; legacy.erase("enabled_contexts"); legacy.erase("suppressed_actions"); RestoreInputCheckpoint(loaded,legacy);
    Check("Legacy version-four input upgrades without inventing contexts",loaded.input.contexts.empty() && InputCheckpoint(loaded)["version"]==5);
}
}
int main() {
    Json report={{"passed",false}};
    try { Core(); VirtualDevice(); Mappings(); ContextChecks(); report["passed"]=true; }
    catch(const std::exception& e) { report["error"]=e.what(); }
    report["checks"]=checks; std::cout<<report.dump(2)<<"\n"; return report["passed"].get<bool>()?0:1;
}
