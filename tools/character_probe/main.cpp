#include "physics_world.hpp"
#include "../../runtime/third_party/picosha2/picosha2.hpp"
#include <fstream>
#include <iostream>

using namespace rt;
namespace {
Json checks=Json::array();
void Check(bool ok,const std::string& label) { if(!ok) throw std::runtime_error(label); checks.push_back(label); }
bool Near(double a,double b,double tolerance=.03) { return std::abs(a-b)<=tolerance; }
void Steps(PhysicsWorld& world,int count) { for(int i=0;i<count;++i) world.step(1./60); }
PhysicsBody Box(std::string id,Vec3 p,Vec3 half,std::string motion="static") {
    PhysicsBody b; b.id=id; b.position=p; b.half_extents=half; b.motion=motion; return b;
}
void Floor(PhysicsWorld& w) { w.add(Box("floor",{0,-.5,0},{30,.5,30})); }
void Hero(PhysicsWorld& w,Vec3 p={0,3,0}) {
    PhysicsBody b; b.id="hero"; b.shape="capsule"; b.motion="kinematic"; b.position=p;
    b.radius=.3; b.half_height=.6; b.mass=70; w.add(b); w.attach_character("hero");
}
Json State(const PhysicsWorld& w) {
    const auto c=w.character_state("hero");
    return {{"position",ToJson(c.position)},{"velocity",ToJson(c.velocity)},
        {"grounded",c.grounded},{"ground",c.ground_entity},{"normal",ToJson(c.ground_normal)},
        {"ground_velocity",ToJson(c.ground_velocity)},{"ground_state",c.ground_state}};
}
template<class F> void Reject(PhysicsWorld& w,const std::string& label,F operation) {
    auto before=w.checkpoint(); bool failed=false;
    try { operation(); } catch(const std::exception&) { failed=true; }
    Check(failed,label); Check(w.checkpoint()==before,label+" leaves the world unchanged");
}
void Basics() {
    PhysicsWorld w; Floor(w); Hero(w);
    auto initial=w.checkpoint(); PhysicsWorld restored; restored.restore(initial);
    Check(restored.checkpoint()==initial,"Character checkpoint restores before the first step");
    Steps(w,120); auto c=w.character_state("hero");
    Check(c.grounded&&c.ground_entity=="floor"&&Near(c.position.y,.92)&&c.ground_normal.y>.99,"Character falls and rests on its lower capsule");
    const auto x=c.position.x; w.character_move("hero",{2,0,0}); Steps(w,30);
    Check(Near(w.pose("hero").position.x-x,1),"Desired horizontal velocity advances the visible capsule once per step");
    w.character_move("hero",Vec3(0));
    Check(w.character_jump("hero",5)&&!w.character_jump("hero",5),"Grounded jump queues once");
    w.step(1./60);
    Check(w.character_state("hero").velocity.y>4&&!w.character_jump("hero",5),"Jump rises and rejects an airborne second jump");
    Steps(w,100); c=w.character_state("hero");
    Check(c.grounded&&Near(c.position.y,.92),"Character lands after jumping");
    w.ignore_pair("hero","floor",true); Check(!w.character_state("hero").grounded,"Ignoring a support immediately clears reported grounding");
    w.ignore_pair("hero","floor",false); w.filter("floor",0,0);
    Check(!w.character_state("hero").grounded,"Support mask changes immediately clear reported grounding");
    w.filter("floor",0,~0u);
    Check(w.raycast(c.position+Vec3(0,4,0),{0,-10,0}).entity=="hero","Ray queries see the character's capsule body");
    Check(w.overlap_sphere(c.position,.05)==std::vector<std::string>{"hero"},"Overlap queries see the character's capsule body");
    w.enabled("hero",false); auto before=State(w); w.character_move("hero",{2,0,0}); Steps(w,20);
    Check(State(w)==before&&!w.character_jump("hero",5),"Disabled character freezes and cannot jump");
    Check(w.overlap_sphere(c.position,.05).empty(),"Disabled character disappears from overlap queries");
    w.enabled("hero",true); Steps(w,30);
    Check(w.character_state("hero").position.x>c.position.x+.9,"Reenabled character resumes its requested movement");
    w.transform("hero",{0,3,0},{1,0,0,0}); w.velocity("hero",Vec3(0),Vec3(0));
    Check(!w.character_state("hero").grounded&&w.character_state("hero").position==Vec3(0,3,0),"Teleport synchronizes capsule and clears old grounding");
    Steps(w,120); const auto foot=w.pose("hero").position.y-.9;
    Check(w.character_resize("hero",.3,.2)&&Near(w.pose("hero").position.y-.5,foot,.001),"Crouch changes capsule size while preserving feet");
    w.add(Box("ceiling",{0,1.4,0},{2,.1,2})); const auto crouched=w.checkpoint();
    Check(!w.character_resize("hero",.3,.6)&&w.checkpoint()==crouched,"Ceiling blocks standing without changing character or body state");
    w.remove("ceiling"); Check(w.character_resize("hero",.3,.6),"Standing succeeds after ceiling removal");
    w.add(Box("ceiling",{0,2.1,0},{2,.1,2})); Check(w.character_jump("hero",5),"Jump starts below a low ceiling");
    double peak=0; for(int i=0;i<60;++i) { w.step(1./60); peak=std::max(peak,w.pose("hero").position.y); }
    Check(peak<1.12&&w.character_state("hero").grounded,"Jump hits the ceiling and returns to the floor");
    w.remove("hero"); Check(!w.has_character("hero")&&!w.contains("hero"),"Body removal also removes its controller");
}
void WallsStepsAndSlopes() {
    PhysicsWorld w; Floor(w); w.add(Box("wall",{2,2,0},{.25,2,10})); Hero(w,{0,.92,-2});
    w.character_move("hero",{2,0,1}); Steps(w,120); auto c=w.character_state("hero");
    Check(c.position.x<1.46&&c.position.x>1.35&&c.position.z>-.2,"Character slides along a blocking wall");
    w.transform("hero",{0,.92,0},{1,0,0,0}); w.character_move("hero",{1000,0,0}); w.step(1./60);
    Check(w.pose("hero").position.x<1.46,"Fast character sweep does not tunnel through a wall");
    w.character_move("hero",{2,0,0}); w.ignore_pair("hero","wall",true); Steps(w,30);
    Check(w.pose("hero").position.x>2.2,"Character collision respects ignored body pairs");
    w.ignore_pair("hero","wall",false); w.transform("hero",{0,.92,0},{1,0,0,0}); w.filter("wall",0,0); Steps(w,90);
    Check(w.pose("hero").position.x>2.9,"Character collision respects the target body's mask");
    w.filter("wall",1,~0u); w.filter("hero",0,1); w.transform("hero",{0,.92,0},{1,0,0,0}); Steps(w,90);
    Check(w.pose("hero").position.x>2.9,"Character collision respects its own layer mask");
    PhysicsWorld steps; Floor(steps); Hero(steps,{0,.92,0}); steps.add(Box("step",{2,.1,0},{.5,.1,2}));
    steps.character_move("hero",{2,0,0}); double peak=0;
    for(int i=0;i<120;++i) { steps.step(1./60); peak=std::max(peak,steps.pose("hero").position.y); }
    Check(steps.pose("hero").position.x>3.8&&peak>1.08&&Near(steps.pose("hero").position.y,.92),"Character climbs a low step and follows the floor back down");
    steps.transform("hero",{0,.92,0},{1,0,0,0}); steps.shape("step",{.5,.5,2},.5,.5); steps.transform("step",{2,.5,0},{1,0,0,0}); Steps(steps,100);
    Check(steps.pose("hero").position.x<1.25,"A step above the configured height blocks movement");
    for(double limit:{45.,15.}) {
        PhysicsWorld slope; Floor(slope); auto ramp=Box("ramp",{4,1.5,0},{4,.2,3});
        ramp.rotation=glm::angleAxis(glm::radians(25.),Vec3(0,0,1)); slope.add(ramp); Hero(slope,{-1,.92,0});
        auto config=slope.character_settings("hero"); config.max_slope=limit; slope.configure_character("hero",config);
        slope.character_move("hero",{2,0,0}); Steps(slope,150); auto p=slope.pose("hero").position;
        Check(limit>25?(p.x>3&&p.y>2):(p.x<2&&p.y<2),limit>25?"Walkable slope raises the character":"Steep slope prevents climbing");
    }
}
void PlatformsAndPush() {
    PhysicsWorld w; w.add(Box("platform",{0,-.25,0},{3,.25,3},"kinematic")); Hero(w,{0,2,0}); Steps(w,60);
    w.velocity("platform",{1,0,0},Vec3(0)); const auto x=w.pose("hero").position.x; Steps(w,60);
    Check(Near(w.pose("hero").position.x-x,1,.06)&&w.character_state("hero").ground_entity=="platform","Character follows the velocity of its moving support");
    w.remove("platform"); Check(!w.character_state("hero").grounded,"Removed support no longer reports grounded");
    Steps(w,30); Check(w.pose("hero").position.y<0,"Character falls after support removal");
    PhysicsWorld pushed; Floor(pushed); Hero(pushed,{0,.92,0}); auto box=Box("crate",{1,.5,0},{.5,.5,.5},"dynamic");
    box.mass=2; box.friction=0; pushed.add(box); pushed.character_move("hero",{2,0,0}); Steps(pushed,90);
    Check(pushed.pose("crate").position.x>2,"Character pushes a dynamic body through Jolt");
}
void ContactEvents() {
    PhysicsWorld w; Floor(w); Hero(w);
    auto zone=Box("zone",{0,2,0},{1,3,1}); zone.sensor=true; w.add(zone);
    int landing=0,staying=0,enter=0; bool payload=true;
    for(int frame=0;frame<120;++frame) {
        w.step(1./60);
        for(const auto& e:w.contacts()) {
            if(e.first=="floor"&&e.second=="hero") {
                landing+=e.phase=="enter"; staying+=e.phase=="stay";
                payload=payload&&!e.sensor&&e.normal.y>.9&&std::abs(e.point.y)<.03;
            }
            if(e.first=="hero"&&e.second=="zone"&&e.sensor&&e.phase=="enter") ++enter;
        }
    }
    Check(landing==1&&staying>30,"Character collision reports one landing Enter and persistent Stay");
    Check(payload,"Character floor events keep oriented surface payloads");
    Check(enter==1,"Character detects a static trigger exactly once");
    auto has=[&](const std::string& a,const std::string& b,const std::string& phase,bool sensor=false) {
        return std::count_if(w.contacts().begin(),w.contacts().end(),[&](const auto& e) {
            return e.first==a&&e.second==b&&e.phase==phase&&e.sensor==sensor;
        })==1;
    };
    w.character_move("hero",{2,0,0}); int exits=0;
    for(int i=0;i<60;++i) { w.step(1./60); exits+=has("hero","zone","exit",true); }
    Check(exits==1&&w.pose("hero").position.x>1.9,"Character walks through a trigger and emits exactly one Exit");
    w.character_move("hero",Vec3(0)); w.enabled("hero",false); w.step(1./60);
    Check(has("floor","hero","exit"),"Disabling a character emits its final collision Exit");
    w.step(1./60); Check(w.contacts().empty(),"Disabled character produces no repeated contact events");
    w.enabled("hero",true); w.step(1./60);
    Check(has("floor","hero","enter"),"Reenabled character emits a fresh collision Enter");
    w.detach_character("hero");
    PhysicsWorld detached; detached.restore(w.checkpoint()); w.step(1./60); detached.step(1./60);
    Check(detached.checkpoint()==w.checkpoint(),"Checkpoint after detach preserves pending contact removal");
    Check(has("floor","hero","exit"),"Detaching restores ordinary kinematic contact filtering");
    w.attach_character("hero");
    PhysicsWorld reattached; reattached.restore(w.checkpoint()); w.step(1./60); reattached.step(1./60);
    Check(reattached.checkpoint()==w.checkpoint(),"Checkpoint after reattach preserves new contact generation");
    Check(has("floor","hero","enter"),"Reattaching restores character contact delivery");
    w.ignore_pair("floor","hero",true); w.step(1./60);
    Check(has("floor","hero","exit"),"Ignoring a pair terminates character collision events");
    w.ignore_pair("floor","hero",false); w.transform("hero",{0,.9,0},{1,0,0,0}); w.velocity("hero",Vec3(0),Vec3(0)); w.step(1./60);
    Check(has("floor","hero","enter")&&has("hero","zone","enter",true),"Teleport refreshes solid and trigger contact pairs");
    w.filter("zone",0,0); w.step(1./60);
    Check(has("hero","zone","exit",true)&&has("floor","hero","stay"),"Trigger mask changes preserve unrelated character contacts");
    w.filter("zone",0,~0u); w.step(1./60);
    Check(has("hero","zone","enter",true),"Restored trigger mask emits Enter again");
    w.remove("zone"); w.step(1./60);
    Check(has("hero","zone","exit",true),"Removed trigger still emits a final character Exit");
    w.remove("hero"); Hero(w,{0,.9,0}); w.step(1./60);
    Check(has("floor","hero","exit")&&has("floor","hero","enter"),"Recreated character keeps old Exit and new Enter distinct");
    Check(w.contacts().front().phase=="exit","Recreated character emits Exit before Enter");
    PhysicsWorld wall; Floor(wall); wall.add(Box("wall",{2,2,0},{.25,2,10})); Hero(wall,{0,.92,0});
    wall.character_move("hero",{2,0,0}); int hits=0,stays=0;
    for(int frame=0;frame<100;++frame) { wall.step(1./60); for(const auto& e:wall.contacts()) if(e.second=="wall") { hits+=e.phase=="enter"; stays+=e.phase=="stay"; } }
    Check(hits==1&&stays>30,"Character wall contact remains stable at its collision margin");
}
void Validation() {
    PhysicsWorld w; Floor(w); Hero(w); Steps(w,90);
    Reject(w,"Duplicate character is rejected",[&]{w.attach_character("hero");});
    Reject(w,"Noncapsule body cannot receive a character",[&]{w.attach_character("floor");});
    Reject(w,"Invalid slope is rejected",[&]{auto c=w.character_settings("hero"); c.max_slope=90; w.configure_character("hero",c);});
    Reject(w,"Invalid movement is rejected",[&]{w.character_move("hero",{0,1,0});});
    Reject(w,"Invalid jump speed is rejected",[&]{w.character_jump("hero",0);});
    Reject(w,"Invalid capsule size is rejected",[&]{w.character_resize("hero",-1,.5);});
    Reject(w,"Character cannot become a dynamic rigid body",[&]{w.motion("hero","dynamic");});
    Reject(w,"Character cannot tilt",[&]{w.transform("hero",Vec3(0),glm::angleAxis(.4,Vec3(1,0,0)));});
    Reject(w,"Character rejects angular velocity",[&]{w.velocity("hero",Vec3(0),{0,1,0});});
    Reject(w,"Character rejects a rigid-body kinematic target",[&]{w.kinematic_target("hero",Vec3(0),{1,0,0,0},1);});
    Reject(w,"Character rejects unchecked shape replacement",[&]{w.shape("hero",Vec3(.5),.3,.3);});
    Reject(w,"Character rejects manual sleeping",[&]{w.awake("hero",false);});
}
void Scenario(PhysicsWorld& w,int scenario) {
    if(scenario==4) w.add(Box("platform",{0,-.25,0},{3,.25,3},"kinematic")); else Floor(w);
    Hero(w); Steps(w,120);
    if(scenario==0||scenario==1||scenario==2) {
        w.character_move("hero",{1,0,0}); Check(w.character_jump("hero",5),"Scenario jump is grounded");
        if(scenario==1) Steps(w,15);
        if(scenario==2) w.enabled("hero",false);
    }
    if(scenario==3) { Check(w.character_resize("hero",.3,.2),"Scenario crouches"); w.add(Box("ceiling",{0,1.4,0},{2,.1,2})); }
    if(scenario==4) { w.velocity("platform",{1,0,0},Vec3(0)); Steps(w,20); }
    if(scenario==5) { w.add(Box("wall",{2,2,0},{.25,2,10})); w.character_move("hero",{2,0,0}); Steps(w,90); }
    if(scenario==6) w.remove("floor");
    if(scenario==7) { w.transform("hero",{0,.2,0},{1,0,0,0}); w.velocity("hero",Vec3(0),Vec3(0)); }
}
void Advance(PhysicsWorld& w,int scenario,int frame) {
    if(scenario==2&&frame==4) w.enabled("hero",true);
    if(scenario==3&&frame==20) Check(!w.character_resize("hero",.3,.6),"Replay ceiling still blocks standing");
    if(scenario==3&&frame==45) { w.remove("ceiling"); Check(w.character_resize("hero",.3,.6),"Replay stands after ceiling removal"); }
    if(scenario==5&&frame==20) w.character_move("hero",{0,0,2});
    w.step(1./60);
}
std::string Hash(const PhysicsWorld& w) { return picosha2::hash256_hex_string(w.checkpoint().dump()); }
Json Checkpoints() {
    Json cases=Json::array();
    for(int scenario=0;scenario<8;++scenario) {
        PhysicsWorld original; Scenario(original,scenario); auto saved=original.checkpoint(); PhysicsWorld restored; restored.restore(saved);
        Check(restored.checkpoint()==saved,"Character scenario "+std::to_string(scenario)+" restores exactly");
        Json trace=Json::array();
        for(int frame=0;frame<140;++frame) {
            Advance(original,scenario,frame); Advance(restored,scenario,frame);
            auto expected=Hash(original);
            if(expected!=Hash(restored)) throw std::runtime_error("Scenario "+std::to_string(scenario)+" diverged at frame "+std::to_string(frame));
            trace.push_back(expected);
        }
        Check(true,"Character scenario "+std::to_string(scenario)+" matches 140 continuation frames");
        cases.push_back({{"checkpoint",saved},{"trace",trace}});
    }
    return cases;
}
void Corruption() {
    PhysicsWorld w; Floor(w); Hero(w); Steps(w,120); const auto good=w.checkpoint();
    auto reject=[&](const std::string& name,auto edit) { auto bad=good; edit(bad); Reject(w,name,[&]{w.restore(bad);}); };
    reject("Unknown character checkpoint field is rejected",[](Json& j){j["characters"]["hero"]["unknown"]=true;});
    reject("Missing character body is rejected",[](Json& j){j["characters"]["absent"]=j["characters"]["hero"];});
    reject("Invalid character configuration is rejected",[](Json& j){j["characters"]["hero"]["settings"]["step_height"]=-1;});
    reject("Invalid queued movement is rejected",[](Json& j){j["characters"]["hero"]["desired"]={0,1,0};});
    reject("Invalid queued jump is rejected",[](Json& j){j["characters"]["hero"]["jump"]=-1;});
    reject("Truncated character state is rejected",[](Json& j){j["characters"]["hero"]["state"]="0000";});
    reject("Trailing character state is rejected",[](Json& j){j["characters"]["hero"]["state"].get_ref<std::string&>()+="00";});
    reject("Invalid character ground enum is rejected",[](Json& j){j["characters"]["hero"]["state"].get_ref<std::string&>().replace(0,8,"ffffffff");});
    reject("Unbounded character contact allocation is rejected",[](Json& j){j["characters"]["hero"]["state"].get_ref<std::string&>().replace(117*2,8,"ffffffff");});
    reject("Nonfinite character position is rejected",[](Json& j){j["characters"]["hero"]["state"].get_ref<std::string&>().replace(60*2,16,"000000000000f87f");});
    reject("Character and capsule pose disagreement is rejected",[](Json& j){j["characters"]["hero"]["state"].get_ref<std::string&>().replace(60*2,16,"000000000000f03f");});
    reject("Malformed character boolean is rejected",[](Json& j){j["characters"]["hero"]["state"].get_ref<std::string&>().replace(116*2,2,"02");});
}
}
int main(int argc,char** argv) {
    try {
        if(argc==3&&std::string(argv[1])=="--write-checkpoints") {
            auto cases=Checkpoints(); std::ofstream file(argv[2],std::ios::binary); file<<cases.dump();
            if(!file) throw std::runtime_error("Cannot write character checkpoint fixture");
            std::cout<<Json{{"ok",true},{"checks",checks},{"cases",cases.size()},{"frames",1120}}.dump()<<'\n'; return 0;
        }
        if(argc==3&&std::string(argv[1])=="--read-checkpoints") {
            std::ifstream file(argv[2],std::ios::binary); Json cases; file>>cases;
            for(std::size_t i=0;i<cases.size();++i) {
                PhysicsWorld w; w.restore(cases[i]["checkpoint"]);
                Check(w.checkpoint()==cases[i]["checkpoint"],"Fresh-process character scenario "+std::to_string(i)+" recaptures exactly");
                for(int frame=0;frame<int(cases[i]["trace"].size());++frame) {
                    Advance(w,int(i),frame); if(Hash(w)!=cases[i]["trace"][frame].get<std::string>()) throw std::runtime_error("Fresh-process divergence in scenario "+std::to_string(i)+" frame "+std::to_string(frame));
                }
                Check(true,"Fresh-process character scenario "+std::to_string(i)+" matches 140 frames");
            }
            std::cout<<Json{{"ok",true},{"checks",checks}}.dump()<<'\n'; return 0;
        }
        Basics(); WallsStepsAndSlopes(); PlatformsAndPush(); ContactEvents(); Validation(); Corruption();
        std::cout<<Json{{"ok",true},{"checks",checks}}.dump()<<'\n'; return 0;
    } catch(const std::exception& error) { std::cout<<Json{{"ok",false},{"checks",checks},{"error",error.what()}}.dump()<<'\n'; return 1; }
}
