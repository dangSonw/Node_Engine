#include "physics_world.hpp"
#include <iostream>
#include <limits>
#include <fstream>
#include "../../runtime/third_party/picosha2/picosha2.hpp"

using namespace rt;
namespace {
Json checks=Json::array();
void Check(bool ok,const std::string& message) {
    if(!ok) throw std::runtime_error(message);
    checks.push_back(message);
}
bool Near(double a,double b,double epsilon=.025) { return std::abs(a-b)<=epsilon; }
template<class F> void Fails(const std::string& message,F action) {
    bool failed=false; try { action(); } catch(const std::exception&) { failed=true; }
    Check(failed,message);
}
PhysicsBody Body(std::string id,Vec3 position=Vec3(0),std::string shape="box",std::string motion="dynamic") {
    PhysicsBody b; b.id=std::move(id); b.position=position; b.shape=std::move(shape); b.motion=std::move(motion); return b;
}
void Steps(PhysicsWorld& w,int count) { for(int i=0;i<count;++i) w.step(1./60); }
Json Pose(const PhysicsWorld& w,const std::string& id) {
    auto p=w.pose(id); return {{"position",ToJson(p.position)},{"velocity",ToJson(p.velocity)},
        {"angular_velocity",ToJson(p.angular_velocity)},{"rotation",{p.rotation.w,p.rotation.x,p.rotation.y,p.rotation.z}},{"awake",p.awake}};
}
Json Contacts(const PhysicsWorld& w) {
    auto result=Json::array();
    for(const auto& c:w.contacts()) result.push_back({{"first",c.first},{"second",c.second},{"phase",c.phase},
        {"point",ToJson(c.point)},{"normal",ToJson(c.normal)},{"sensor",c.sensor}});
    return result;
}
bool Contact(const PhysicsWorld& w,const std::string& phase,bool sensor=false) {
    for(const auto& c:w.contacts()) if(c.phase==phase&&c.sensor==sensor) return true;
    return false;
}
void ShapeQueries() {
    PhysicsWorld w;
    auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={10,.5,10}; w.add(floor);
    auto query=Body("query",{0,5,0},"sphere"); const Vec3 down{0,-10,0};
    const auto unchanged=w.checkpoint();
    auto hit=w.cast_shape(query,down);
    Check(hit.hit&&hit.entity=="floor"&&Near(hit.fraction,.45,.0001)&&Near(hit.point.y,0,.0001)&&hit.normal.y>.999,
          "Sphere cast returns nearest fraction, target surface point and outward normal");
    query.shape="box"; query.half_extents={.25,1,.5}; hit=w.cast_shape(query,down);
    Check(hit.hit&&Near(hit.fraction,.4,.0001),"Box cast respects its half extents");
    query.rotation=glm::angleAxis(glm::radians(90.),Vec3(0,0,1)); hit=w.cast_shape(query,down);
    Check(hit.hit&&Near(hit.fraction,.475,.0001)&&hit.normal.y>.999,"Box cast respects query rotation");
    query.shape="capsule"; query.radius=.25; query.half_height=.75; query.rotation={1,0,0,0}; hit=w.cast_shape(query,down);
    Check(hit.hit&&Near(hit.fraction,.4,.0001),"Y capsule cast includes cylinder and spherical caps");
    query.rotation=glm::angleAxis(glm::radians(90.),Vec3(0,0,1)); hit=w.cast_shape(query,down);
    Check(hit.hit&&Near(hit.fraction,.475,.0001),"Capsule cast respects query rotation");
    Check(!w.cast_shape(query,down,~0u,false,"floor").hit,"Shape cast excludes the requested body");
    Check(!w.cast_shape(query,down,0).hit,"Shape cast honors an empty query mask");
    query.position={20,5,0}; hit=w.cast_shape(query,down);
    Check(!hit.hit&&hit.entity.empty()&&hit.point==Vec3(0)&&hit.normal==Vec3(0)&&hit.fraction==1,"Shape miss returns a complete fresh empty result");
    query.shape="sphere"; query.radius=.5; query.rotation={1,0,0,0}; query.position={0,.25,0};
    hit=w.cast_shape(query,{0,2,0});
    Check(hit.hit&&hit.fraction==0&&hit.normal.y>.99,"Initially overlapping cast reports contact while moving away");
    Check(w.cast_shape(query,Vec3(0)).hit,"Zero displacement shape cast detects initial overlap");
    query.position={0,5,0}; Check(!w.cast_shape(query,Vec3(0)).hit,"Stationary separated cast misses");
    Check(w.checkpoint()==unchanged,"Queries do not mutate native bodies, contacts or checkpoint bytes");
    w.filter("floor",31,~0u);
    Check(w.cast_shape(query,down,1u<<31).hit&&!w.cast_shape(query,down,1).hit,"Shape query masks support layer 31");
    w.enabled("floor",false); Check(!w.cast_shape(query,down).hit,"Disabled bodies are excluded from shape casts");
    w.enabled("floor",true);
    auto sensor=Body("sensor",{0,2,0},"box","static"); sensor.sensor=true; w.add(sensor);
    Check(w.cast_shape(query,down).entity=="floor"&&w.cast_shape(query,down,~0u,true).entity=="sensor","Shape casts optionally include nearer triggers");
    w.transform("floor",{1e8,-.5,0},{1,0,0,0}); query.position={1e8,5,0}; hit=w.cast_shape(query,down);
    Check(hit.hit&&Near(hit.point.x,1e8,.001)&&Near(hit.point.y,0,.001),"Shape cast target point stays accurate far from origin");
    Fails("Shape cast rejects invalid query dimensions",[&]{auto invalid=query; invalid.radius=-1; w.cast_shape(invalid,down);});
    Fails("Shape cast rejects invalid query rotation",[&]{auto invalid=query; invalid.rotation={0,0,0,0}; w.cast_shape(invalid,down);});
    Fails("Shape cast rejects excessive displacement",[&]{w.cast_shape(query,{1e8,0,0});});
}
void ShapeOverlaps() {
    PhysicsWorld w;
    auto target=Body("zeta",{-1,1,0},"box","static"); target.half_extents=Vec3(.05); w.add(target);
    target.id="alpha"; target.position=Vec3(0); target.layer=31; w.add(target);
    target.id="corner"; target.position={1,1,0}; target.layer=0; w.add(target);
    target.id="sensor"; target.position={-.5,.5,0}; target.sensor=true; w.add(target);
    auto query=Body("query"); query.half_extents={.15,2,.15}; query.radius=.2; query.half_height=2;
    query.rotation=glm::angleAxis(glm::radians(45.),Vec3(0,0,1));
    const auto unchanged=w.checkpoint();
    for(const auto* shape:{"box","capsule"}) {
        query.shape=shape; const auto label=std::string(shape)+" overlap ";
        Check(w.overlap_shape(query)==std::vector<std::string>{"alpha","zeta"},label+"uses oriented narrow-phase geometry and sorted unique IDs");
        Check(w.overlap_shape(query,~0u,true)==std::vector<std::string>{"alpha","sensor","zeta"},label+"includes triggers when requested");
        Check(w.overlap_shape(query,1u<<31)==std::vector<std::string>{"alpha"},label+"honors layer 31");
        Check(w.overlap_shape(query,~0u,false,"alpha")==std::vector<std::string>{"zeta"},label+"excludes the requested body");
        Check(w.overlap_shape(query,0).empty(),label+"honors an empty mask");
        auto upright=query; upright.rotation={1,0,0,0};
        Check(w.overlap_shape(upright)==std::vector<std::string>{"alpha"},label+"changes with query rotation");
        auto missed=query; missed.position={0,0,10};
        Check(w.overlap_shape(missed).empty(),label+"returns no stale IDs on a miss");
    }
    query.shape="sphere"; query.radius=1.6;
    Check(w.overlap_shape(query)==w.overlap_sphere(query.position,query.radius),"Generic sphere overlap preserves the existing sphere query");
    Check(w.checkpoint()==unchanged,"All overlap queries preserve bodies, contacts and checkpoint bytes");
    query.shape="capsule"; query.radius=.2;
    w.enabled("zeta",false);
    Check(w.overlap_shape(query)==std::vector<std::string>{"alpha"},"Overlap excludes disabled bodies");
    w.enabled("zeta",true); w.remove("alpha");
    Check(w.overlap_shape(query)==std::vector<std::string>{"zeta"},"Overlap reflects body removal immediately");
    w.transform("zeta",{1e8-1,1,0},{1,0,0,0}); query.position={1e8,0,0};
    Check(w.overlap_shape(query)==std::vector<std::string>{"zeta"},"Oriented overlap retains precision far from origin");
    Fails("Overlap rejects zero capsule half height",[&]{auto bad=query; bad.half_height=0; w.overlap_shape(bad);});
    Fails("Overlap rejects invalid rotation",[&]{auto bad=query; bad.rotation={0,0,0,0}; w.overlap_shape(bad);});
    Fails("Overlap rejects nonfinite dimensions",[&]{auto bad=query; bad.radius=std::numeric_limits<double>::quiet_NaN(); w.overlap_shape(bad);});
    PhysicsWorld empty;
    Fails("Empty-world overlap still validates dimensions",[&]{auto bad=query; bad.shape="box"; bad.half_extents.x=-1; empty.overlap_shape(bad);});
}
void Drop() {
    PhysicsWorld w;
    auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={20,.5,20}; w.add(floor);
    w.add(Body("box",{-3,4,0})); w.add(Body("sphere",{0,5,0},"sphere")); w.add(Body("capsule",{3,6,0},"capsule"));
    Steps(w,10); Check(w.pose("box").position.y<4,"Gravity moves dynamic bodies");
    bool entered=false,stayed=false;
    for(int i=0;i<350;++i) { w.step(1./60); entered|=Contact(w,"enter"); stayed|=Contact(w,"stay"); }
    Check(Near(w.pose("box").position.y,.5),"Box rests on floor");
    Check(Near(w.pose("sphere").position.y,.5),"Sphere rests on floor");
    Check(Near(w.pose("capsule").position.y,1),"Upright capsule rests on floor");
    Check(w.pose("floor").position.y==-.5,"Static floor never moves");
    Check(!w.pose("box").awake,"Settled body sleeps");
    Check(Contact(w,"stay")&&!Contact(w,"exit"),"Sleeping bodies retain contact stay without a false exit");
    Check(entered&&stayed,"Contact enter and stay are emitted");
    w.impulse("box",{0,4,0}); Steps(w,8);
    Check(w.pose("box").position.y> .8&&w.pose("box").awake,"Impulse wakes a sleeping body");
    auto hit=w.raycast({0,10,0},{0,-20,0});
    Check(hit.hit&&hit.entity=="sphere"&&Near(hit.point.y,1)&&hit.normal.y>.99,"Raycast returns closest entity point and normal");
    hit=w.raycast({0,10,0},{0,-20,0},~0u,false,"sphere");
    Check(hit.hit&&hit.entity=="floor"&&Near(hit.fraction,.5,.001),"Raycast exclusion reveals floor");
    Check(!w.raycast({30,10,0},{0,-20,0}).hit,"Raycast miss");
    w.filter("sphere",31,~0u);
    Check(w.raycast({0,10,0},{0,-20,0},1u<<31).entity=="sphere","Query supports unsigned layer 31");
    Check(!w.raycast({0,10,0},{0,-20,0},2).hit,"Raycast respects query mask");
    auto overlaps=w.overlap_sphere({0,.5,0},.1);
    Check(overlaps==std::vector<std::string>{"sphere"},"Sphere overlap uses exact shape");
    Check(w.overlap_sphere({0,.5,0},.1,~0u,false,"sphere").empty(),"Overlap exclusion");
    Check(w.overlap_sphere({0,.5,0},.1,1).empty(),"Overlap layer mask");
    hit=w.raycast(w.pose("sphere").position,{0,0,4});
    Check(hit.hit&&hit.entity=="sphere"&&hit.fraction==0&&hit.normal==Vec3(0,0,-1),"Ray inside sphere returns a finite opposing normal");
    w.enabled("sphere",false);
    Check(w.raycast({0,10,0},{0,-20,0}).entity=="floor","Disabled body leaves collision queries");
    auto before=Pose(w,"sphere"); Steps(w,30);
    Check(Pose(w,"sphere")==before,"Disabled body stops simulation");
    w.enabled("sphere",true); Check(w.raycast({0,10,0},{0,-20,0}).entity=="sphere","Reenabled body returns to broadphase");
}
void Forces() {
    PhysicsWorld w{Vec3(0)};
    auto b=Body("body"); b.mass=2; b.linear_damping=b.angular_damping=0; w.add(b);
    w.impulse("body",{4,0,0}); Check(Near(w.pose("body").velocity.x,2,1e-6),"Impulse respects mass");
    w.velocity("body",Vec3(0),Vec3(0)); w.force("body",{12,0,0},{0,0,1}); w.step(1./60);
    Check(Near(w.pose("body").velocity.x,.1,1e-6),"Force integrates for one fixed step");
    Check(w.pose("body").angular_velocity.z>0,"Torque produces angular motion");
    double velocity=w.pose("body").velocity.x; w.step(1./60);
    Check(Near(w.pose("body").velocity.x,velocity,1e-6),"Forces clear after each fixed step");
    w.mass("body",4); w.velocity("body",Vec3(0),Vec3(0)); w.impulse("body",{4,0,0});
    Check(Near(w.pose("body").velocity.x,1,1e-6),"Changing mass recalculates inertia and impulse response");
    w.damping("body",2,2); w.velocity("body",{2,0,0},{0,0,2}); Steps(w,30);
    Check(w.pose("body").velocity.x<1&&w.pose("body").angular_velocity.z<1,"Linear and angular damping decay velocities");
    w.gravity({0,-10,0}); w.damping("body",0,0); w.gravity_scale("body",2); w.velocity("body",Vec3(0),Vec3(0)); Steps(w,6);
    Check(Near(w.pose("body").velocity.y,-2,1e-5),"Per-body gravity scale");
    w.gravity_scale("body",0); w.velocity("body",Vec3(0),Vec3(0)); Steps(w,6);
    Check(w.pose("body").velocity==Vec3(0),"Zero gravity scale");
    w.awake("body",false); Check(!w.pose("body").awake,"Explicit sleep");
    w.awake("body",true); Check(w.pose("body").awake,"Explicit wake");
    w.motion("body","static"); auto before=Pose(w,"body"); Steps(w,4);
    Check(Pose(w,"body")==before,"Dynamic to static transition");
    w.motion("body","kinematic"); w.transform("body",Vec3(0),{1,0,0,0});
    w.kinematic_target("body",{1,0,0},{1,0,0,0},.1); Steps(w,6);
    Check(Near(w.pose("body").position.x,1,1e-5),"Kinematic target reaches its destination");
    w.motion("body","dynamic"); w.gravity_scale("body",1); w.velocity("body",Vec3(0),Vec3(0)); Steps(w,2);
    Check(w.pose("body").velocity.y<0,"Kinematic to dynamic transition");
    w.enabled("body",false); w.velocity("body",{1,2,3},Vec3(0));
    Check(!w.pose("body").awake,"Velocity edit does not activate disabled body");
    w.transform("body",{4,5,6},{2,0,0,0});
    Check(w.pose("body").position==Vec3(4,5,6)&&!w.pose("body").awake,"Disabled transform edits normalize rotation without waking");
    w.enabled("body",true); Steps(w,1); Check(w.pose("body").position.x>4,"Disabled velocity edit survives reenable");
}
void FilteringAndTriggers() {
    PhysicsWorld w;
    auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={10,.5,10}; floor.layer=2; floor.mask=1u<<1; w.add(floor);
    auto good=Body("good",{-2,2,0}); good.layer=1; good.mask=1u<<2; w.add(good);
    auto wrong=Body("wrong",{2,2,0}); wrong.layer=1; wrong.mask=1; w.add(wrong);
    Steps(w,90);
    Check(Near(w.pose("good").position.y,.5)&&w.pose("wrong").position.y< -1,"Collision requires both layer masks to accept");
    w.ignore_pair("good","floor",true); Steps(w,60);
    Check(w.pose("good").position.y< -1,"Ignoring an established pair removes collision");
    w.ignore_pair("floor","good",false); w.transform("good",{-2,2,0},{1,0,0,0}); w.velocity("good",Vec3(0),Vec3(0)); Steps(w,90);
    Check(Near(w.pose("good").position.y,.5),"Restoring pair collisions works in reverse entity order");
    w.filter("wrong",1,1u<<2); w.transform("wrong",{2,2,0},{1,0,0,0}); w.velocity("wrong",Vec3(0),Vec3(0)); Steps(w,90);
    Check(Near(w.pose("wrong").position.y,.5),"Runtime filter changes update collision behaviour");
    PhysicsWorld triggers{Vec3(0)};
    auto sensor=Body("a-trigger",Vec3(0),"box","static"); sensor.sensor=true; triggers.add(sensor);
    auto visitor=Body("z-visitor",{-2,0,0}); visitor.velocity={2,0,0}; visitor.linear_damping=0; triggers.add(visitor);
    Check(!triggers.raycast({0,3,0},{0,-6,0}).hit,"Ray queries exclude sensors by default");
    Check(triggers.raycast({0,3,0},{0,-6,0},~0u,true).entity=="a-trigger","Ray query can include sensors");
    Check(triggers.overlap_sphere(Vec3(0),.1).empty()&&triggers.overlap_sphere(Vec3(0),.1,~0u,true).size()==1,"Overlap sensor policy");
    bool enter=false,stay=false,exit=false,normal=false;
    for(int i=0;i<150;++i) {
        triggers.step(1./60); enter|=Contact(triggers,"enter",true); stay|=Contact(triggers,"stay",true); exit|=Contact(triggers,"exit",true);
        for(const auto& c:triggers.contacts()) if(c.phase=="enter") normal=c.first=="a-trigger"&&c.second=="z-visitor"&&c.normal.x<-.9;
    }
    Check(enter&&stay&&exit,"Trigger emits enter stay exit");
    Check(normal,"Contact entity ordering preserves normal direction");
    Check(Near(triggers.pose("z-visitor").position.x,3,.001),"Trigger does not block motion");
    triggers.transform("z-visitor",Vec3(0),{1,0,0,0}); triggers.velocity("z-visitor",Vec3(0),Vec3(0)); Steps(triggers,1);
    triggers.remove("z-visitor"); Steps(triggers,1);
    Check(Contact(triggers,"exit",true),"Body removal emits trigger exit");
    Check(!triggers.contains("z-visitor")&&triggers.size()==1,"Body removal releases ownership");
    triggers.add(Body("z-visitor")); Steps(triggers,1);
    Check(Contact(triggers,"enter",true),"Reusing an entity ID creates a new contact");
    triggers.remove("z-visitor"); triggers.add(Body("z-visitor")); Steps(triggers,1);
    Check(Contact(triggers,"enter",true)&&Contact(triggers,"exit",true),"Remove and recreate before stepping preserves distinct contacts");
    Check(triggers.contacts().front().phase=="exit","Replacement emits exit before enter for the same entity pair");
    Steps(triggers,120);
    Check(!triggers.pose("z-visitor").awake&&Contact(triggers,"stay",true),"Sleeping visitor remains inside a static trigger");
    triggers.transform("z-visitor",{5,0,0},{1,0,0,0},false); Steps(triggers,1);
    Check(Contact(triggers,"exit",true),"Teleport without wake still ends a sleeping trigger contact");
    Steps(triggers,1); Check(triggers.contacts().empty(),"Sleeping contact exit fires exactly once");
}
void MaterialAndLifecycle() {
    PhysicsWorld bounce,inelastic;
    auto setup=[](PhysicsWorld& w,double restitution) {
        auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={5,.5,5}; w.add(floor);
        auto sphere=Body("sphere",{0,2,0},"sphere"); sphere.linear_damping=0; w.add(sphere);
        w.material("sphere",0,restitution); w.material("floor",0,restitution);
    };
    setup(bounce,1); setup(inelastic,0); double peak=0;
    for(int i=0;i<120;++i) { bounce.step(1./60); inelastic.step(1./60); if(i>45) peak=std::max(peak,bounce.pose("sphere").position.y); }
    Check(peak>1.5&&Near(inelastic.pose("sphere").position.y,.5),"Restitution controls actual bounce height");
    PhysicsWorld friction,slippery;
    auto slide=[](PhysicsWorld& w,double friction) {
        auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={50,.5,50}; floor.friction=friction; w.add(floor);
        auto box=Body("box",{0,.5,0}); box.velocity={4,0,0}; box.friction=friction; box.linear_damping=0; w.add(box);
    };
    slide(friction,1); slide(slippery,0); Steps(friction,90); Steps(slippery,90);
    Check(std::abs(friction.pose("box").velocity.x)<.05&&slippery.pose("box").velocity.x>3.9,"Friction slows a sliding box");
    PhysicsWorld fast;
    auto wall=Body("wall",{0,0,0},"box","static"); wall.half_extents={.025,10,10}; fast.add(wall);
    auto bullet=Body("bullet",{-2,0,0},"sphere"); bullet.radius=.05; bullet.gravity_scale=0; bullet.velocity={400,0,0}; bullet.continuous=true; fast.add(bullet);
    Steps(fast,1); Check(fast.pose("bullet").position.x<0,"Continuous collision stops a fast sphere at a thin wall");
    PhysicsWorld w;
    auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={10,.5,10}; w.add(floor); w.add(Body("box",{0,.5,0})); Steps(w,180);
    Check(!w.pose("box").awake,"Lifecycle scenario has a sleeping body");
    w.transform("floor",{0,-3,0},{1,0,0,0}); Steps(w,30);
    Check(w.pose("box").position.y<0,"Moving a static support wakes supported bodies");
    w.transform("floor",{0,-.5,0},{1,0,0,0}); w.transform("box",{0,.5,0},{1,0,0,0}); w.velocity("box",Vec3(0),Vec3(0)); Steps(w,180);
    w.enabled("floor",false); Steps(w,30);
    Check(w.pose("box").position.y<0,"Disabling a static support wakes supported bodies");
    w.enabled("floor",true); w.transform("box",{0,.5,0},{1,0,0,0}); w.velocity("box",Vec3(0),Vec3(0)); Steps(w,180);
    w.remove("floor"); Steps(w,30);
    Check(w.pose("box").position.y<0,"Removing a static support wakes supported bodies");
    PhysicsWorld paused{Vec3(0)};
    auto moving=Body("moving"); moving.velocity={3,0,0}; moving.angular_velocity={0,2,0}; moving.linear_damping=moving.angular_damping=0; paused.add(moving);
    paused.enabled("moving",false); auto p=paused.pose("moving"); Steps(paused,20);
    Check(p.velocity==Vec3(3,0,0)&&p.angular_velocity==Vec3(0,2,0)&&paused.pose("moving").position==p.position,"Disabling preserves linear and angular velocity");
    paused.enabled("moving",true); Steps(paused,10);
    Check(paused.pose("moving").position.x>.49,"Reenable resumes preserved velocity");
    PhysicsWorld isolated{Vec3(0)}; auto initial=Body("original",Vec3(0),"box","static"); isolated.add(initial);
    isolated.mass("original",2); isolated.gravity_scale("original",0); isolated.motion("original","dynamic"); isolated.impulse("original",{2,0,0});
    Check(Near(isolated.pose("original").velocity.x,1,1e-6),"Originally static body can become dynamic with updated mass");
}
void Validation() {
    PhysicsWorld w; w.add(Body("body"));
    auto before=Pose(w,"body");
    Fails("Duplicate body rejected",[&]{w.add(Body("body"));});
    Fails("Unknown body rejected",[&]{w.remove("missing");});
    Fails("Invalid shape rejected",[&]{w.add(Body("other",Vec3(0),"invalid"));});
    Fails("Invalid mass rejected",[&]{w.mass("body",0);});
    Fails("NaN force rejected",[&]{w.force("body",Vec3(std::numeric_limits<double>::quiet_NaN()));});
    Fails("Infinite position rejected",[&]{w.transform("body",Vec3(INFINITY),{1,0,0,0});});
    Fails("Zero quaternion rejected",[&]{w.transform("body",Vec3(0),{0,0,0,0});});
    Fails("Invalid layer rejected",[&]{w.filter("body",32,~0u);});
    Fails("Invalid damping rejected",[&]{w.damping("body",1,-1);});
    Fails("Invalid material rejected",[&]{w.material("body",.5,2);});
    Fails("Invalid motion type rejected",[&]{w.motion("body","bad");});
    Fails("Dynamic kinematic target rejected",[&]{w.kinematic_target("body",Vec3(0),{1,0,0,0},.1);});
    Fails("Self ignore pair rejected",[&]{w.ignore_pair("body","body",true);});
    Fails("Zero time step rejected",[&]{w.step(0);});
    Fails("Excessive time step rejected",[&]{w.step(1);});
    Fails("Zero ray rejected",[&]{w.raycast(Vec3(0),Vec3(0));});
    Fails("Negative overlap radius rejected",[&]{w.overlap_sphere(Vec3(0),-1);});
    Check(Pose(w,"body")==before&&w.size()==1,"Invalid operations preserve body state");
    w.add(Body("static",Vec3(0),"box","static"));
    Fails("Static force rejected",[&]{w.force("static",Vec3(1));});
    Fails("Static velocity rejected",[&]{w.velocity("static",Vec3(1),Vec3(0));});
    Fails("Static wake rejected",[&]{w.awake("static",true);});
    w.enabled("body",false);
    Fails("Disabled impulse rejected",[&]{w.impulse("body",Vec3(1));});
    PhysicsWorld capacity{Vec3(0)};
    for(std::size_t i=0;i<PhysicsWorld::MaxBodies;++i) capacity.add(Body(std::to_string(i),{double(i)*2,0,0},"box","static"));
    Fails("Body capacity rejects overflow",[&]{capacity.add(Body("overflow"));});
    capacity.remove("0"); capacity.add(Body("replacement",Vec3(0),"box","static"));
    Check(capacity.size()==PhysicsWorld::MaxBodies&&capacity.contains("replacement"),"Removed body capacity can be reused");
}
Json Determinism() {
    PhysicsWorld a,b;
    auto setup=[](PhysicsWorld& w) {
        auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={5,.5,5}; w.add(floor);
        for(int i=0;i<8;++i) { auto p=Body(std::to_string(i),{i%3-1.,2.+i,0},i%2?"box":"sphere"); p.rotation=glm::angleAxis(.17*i,glm::normalize(Vec3(1,2,3))); w.add(p); }
    };
    setup(a); setup(b); Json trace=Json::array();
    for(int frame=0;frame<240;++frame) {
        if(frame==90) { a.impulse("0",{2,3,1}); b.impulse("0",{2,3,1}); }
        a.step(1./60); b.step(1./60);
        Json state=Json::object();
        for(int i=0;i<8;++i) { auto id=std::to_string(i); auto pa=Pose(a,id); if(pa!=Pose(b,id)) throw std::runtime_error("Independent worlds diverged at frame "+std::to_string(frame)); state[id]=pa; }
        state["contacts"]=Contacts(a);
        if(state["contacts"]!=Contacts(b)) throw std::runtime_error("Independent contact events diverged");
        trace.push_back(state);
    }
    Check(true,"Independent worlds match exactly for 240 frames of collisions and impulses");
    return trace;
}
void CheckpointBasics() {
    PhysicsWorld original{Vec3(0)},restored;
    auto empty=original.checkpoint(); restored.restore(empty);
    Check(restored.checkpoint()==empty,"Empty physics world checkpoint roundtrip");
    original.add(Body("z-first",{0,2,0})); original.add(Body("a-second",{2,0,0}));
    auto fresh=original.checkpoint(); restored.restore(fresh);
    Check(restored.checkpoint()==fresh,"Newly created bodies restore before the first step");
    original.force("z-first",{1,3,2},{.1,.2,.3}); original.impulse("a-second",{2,0,0});
    original.enabled("a-second",false);
    auto saved=original.checkpoint(); restored.restore(saved);
    Check(restored.checkpoint()==saved,"Pending force torque and disabled-body state roundtrip");
    for(int i=0;i<120;++i) {
        if(i==5) { original.enabled("a-second",true); restored.enabled("a-second",true); }
        original.step(1./60); restored.step(1./60);
        if(original.checkpoint()!=restored.checkpoint()) throw std::runtime_error("Basic checkpoint continuation differs at "+std::to_string(i));
    }
    Check(true,"Restored forces and activation remain exact for 120 frames");
}
void CheckpointScene(PhysicsWorld& w) {
    auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={10,.5,10}; w.add(floor);
    for(int i=0;i<5;++i) {
        auto b=Body("stack-"+std::to_string(i),{0,.5+1.1*i,0}); b.mass=1.17+i*.39; w.add(b);
    }
    auto ball=Body("ball",{3,3,0},"sphere"); ball.restitution=.7; w.add(ball);
    auto capsule=Body("capsule",{-3,3,0},"capsule"); w.add(capsule);
    auto trigger=Body("trigger",{3,1,0},"box","static"); trigger.half_extents={1,1,1}; trigger.sensor=true; w.add(trigger);
    auto paused=Body("paused",{20,4,0}); paused.velocity={1,2,3}; paused.angular_velocity={.2,.3,.4}; w.add(paused); w.enabled("paused",false);
    auto kine=Body("platform",{-6,1,0},"box","kinematic"); w.add(kine);
}
void CheckpointAdvance(PhysicsWorld& w,int frame) {
    if(!w.contains("floor")) { auto floor=Body("floor",{0,-.5,0},"box","static"); floor.half_extents={10,.5,10}; w.add(floor); }
    if(frame==7) w.force("stack-0",{4,0,0},{0,.1,.1});
    if(frame==16) w.material("ball",.12,.45);
    if(frame==23) w.mass("stack-2",2.34567);
    if(frame==30) w.kinematic_target("platform",{-5.5,1,0},{1,0,0,0},.1);
    if(frame==36) w.velocity("platform",Vec3(0),Vec3(0));
    if(frame==43) w.enabled("paused",true);
    if(frame==47) { w.enabled("paused",false); w.velocity("paused",{3,2,1},Vec3(.4)); }
    if(frame==51) w.ignore_pair("ball","floor",true);
    if(frame==56) w.ignore_pair("ball","floor",false);
    if(frame==62) { w.remove("stack-4"); w.add(Body("stack-4",{0,7,0})); }
    if(frame==69) { w.motion("capsule","kinematic"); w.kinematic_target("capsule",{-2,1,0},{1,0,0,0},.1); }
    if(frame==75) w.motion("capsule","dynamic");
    if(frame==81) w.filter("stack-0",31,1u<<31);
    if(frame==87) w.filter("stack-0",0,~0u);
    if(frame==96) w.impulse("stack-1",{1,5,1});
    w.step(1./60);
}
Json CheckpointScenarios() {
    Json cases=Json::array(); const std::vector<int> points={0,30,45,180,60,80,1,50};
    for(std::size_t scenario=0;scenario<points.size();++scenario) {
        PhysicsWorld w; CheckpointScene(w); Steps(w,points[scenario]);
        if(scenario==1) w.force("stack-2",{1,2,3},{.2,.3,.4});
        if(scenario==2) { w.mass("stack-0",4.321); w.material("ball",.37,.63); w.damping("capsule",.11,.17); w.gravity_scale("ball",.7); }
        if(scenario==4) w.remove("floor");
        if(scenario==5) for(int i=0;i<300;++i) { w.add(Body("temporary",{100,0,0})); w.remove("temporary"); }
        if(scenario==6) {
            auto fast=Body("bullet",{-2,3,0},"sphere"); fast.radius=.05; fast.continuous=true; fast.velocity={400,0,0}; fast.gravity_scale=0; w.add(fast);
            auto wall=Body("wall",{0,3,0},"box","static"); wall.half_extents={.025,3,3}; w.add(wall); Steps(w,1);
        }
        if(scenario==7) w.kinematic_target("platform",{-4,2,0},glm::angleAxis(.3,Vec3(0,1,0)),.1);
        auto saved=w.checkpoint(); PhysicsWorld restored; restored.restore(saved);
        Check(saved==restored.checkpoint(),"Checkpoint scenario "+std::to_string(scenario)+" recaptures exactly");
        Json trace=Json::array();
        for(int frame=0;frame<110;++frame) {
            CheckpointAdvance(w,frame); CheckpointAdvance(restored,frame);
            auto state=w.checkpoint(),other=restored.checkpoint();
            if(state!=other) {
                std::ofstream("physics-checkpoint-expected.json")<<state.dump(2);
                std::ofstream("physics-checkpoint-actual.json")<<other.dump(2);
                throw std::runtime_error("Checkpoint scenario "+std::to_string(scenario)+" diverged at frame "+std::to_string(frame));
            }
            trace.push_back(picosha2::hash256_hex_string(state.dump()));
        }
        Check(true,"Checkpoint scenario "+std::to_string(scenario)+" matches 110 continuation frames");
        cases.push_back({{"checkpoint",saved},{"trace",trace}});
    }
    return cases;
}
void SetNativeWord(Json& state,std::size_t offset,std::uint32_t word) {
    auto& text=state["native"].get_ref<std::string&>(); constexpr char hex[]="0123456789abcdef";
    for(unsigned i=0;i<4;++i) { auto byte=(word>>(8*i))&255; text.at((offset+i)*2)=hex[byte>>4]; text.at((offset+i)*2+1)=hex[byte&15]; }
}
void CheckpointRejection() {
    PhysicsWorld w; CheckpointScene(w); Steps(w,45); const auto good=w.checkpoint();
    auto reject=[&](const char* label,auto modify) {
        auto bad=good; modify(bad); Fails(label,[&]{w.restore(bad);});
        if(w.checkpoint()!=good) throw std::runtime_error("Rejected checkpoint mutated the live world");
    };
    reject("Reject unknown checkpoint version",[](Json& s){s["version"]=2;});
    reject("Reject backend mismatch",[](Json& s){s["backend"]="other";});
    reject("Reject unknown checkpoint fields",[](Json& s){s["unknown"]=true;});
    reject("Reject incomplete generation table",[](Json& s){s["generations"].erase(0);});
    reject("Reject invalid generation",[](Json& s){s["generations"][0]=256;});
    reject("Reject duplicate native body",[](Json& s){s["bodies"].push_back(s["bodies"][0]);});
    reject("Reject invalid body native ID",[](Json& s){s["bodies"][0]["native_id"]=UINT32_MAX;});
    reject("Reject invalid body mass",[](Json& s){s["bodies"][0]["settings"]["mass"]=-1;});
    reject("Reject invalid body flag type",[](Json& s){s["bodies"][0]["enabled"]=1;});
    reject("Reject duplicate active body",[](Json& s){s["active"].push_back(s["active"][0]);});
    reject("Reject unknown active body",[](Json& s){s["active"].push_back(UINT32_MAX);});
    reject("Reject invalid retired ID",[](Json& s){s["retired"].push_back(UINT32_MAX);});
    reject("Reject a live retired ID",[](Json& s){s["retired"].push_back(s["bodies"][0]["native_id"]);});
    reject("Reject truncated native state",[](Json& s){s["native"].get_ref<std::string&>().resize(10);});
    reject("Reject trailing native bytes",[](Json& s){s["native"].get_ref<std::string&>()+="00";});
    reject("Reject nonhex native state",[](Json& s){s["native"].get_ref<std::string&>()[0]='z';});
    reject("Reject invalid native flags",[](Json& s){s["native"].get_ref<std::string&>()[0]='e';});
    reject("Reject native NaN gravity",[](Json& s){SetNativeWord(s,5,0x7fc00000);});
    reject("Reject native excessive body count",[](Json& s){SetNativeWord(s,17,UINT32_MAX);});
    reject("Reject native unknown body ID",[](Json& s){SetNativeWord(s,21,UINT32_MAX);});
    reject("Reject native invalid boolean",[](Json& s){s["native"].get_ref<std::string&>().at(25*2+1)='2';});
    reject("Reject native excessive contact count",[](Json& s){std::size_t offset=21; for(const auto& b:s["bodies"]) if(b["enabled"]==true) offset+=5+b["state"].get<std::string>().size()/2; SetNativeWord(s,offset,UINT32_MAX);});
    reject("Reject disagreement between body snapshots",[](Json& s){s["bodies"][0]["state"].get_ref<std::string&>().at(0)='f';});
    reject("Reject invalid ignored pair",[](Json& s){s["ignored"].push_back({"missing","other"});});
    reject("Reject invalid contact normal",[](Json& s){s["touching"][0]["contact"]["normal"]={0,0,0};});
    Check(w.checkpoint()==good,"Every rejected checkpoint leaves the original world byte-exact");
}
}
int main(int argc,char** argv) {
    try {
        if(argc==3&&std::string(argv[1])=="--write-checkpoints") {
            auto cases=CheckpointScenarios(); std::ofstream output(argv[2],std::ios::binary); output<<cases.dump();
            if(!output) throw std::runtime_error("Cannot write physics checkpoint fixture");
            std::cout<<Json{{"ok",true},{"checks",checks},{"cases",cases.size()},{"frames",880}}.dump()<<'\n'; return 0;
        }
        if(argc==3&&std::string(argv[1])=="--read-checkpoints") {
            std::ifstream input(argv[2],std::ios::binary); Json cases; input>>cases;
            for(std::size_t i=0;i<cases.size();++i) {
                const auto& row=cases.at(i); PhysicsWorld w; w.restore(row.at("checkpoint"));
                Check(w.checkpoint()==row.at("checkpoint"),"Fresh-process scenario "+std::to_string(i)+" recaptures exactly");
                for(int frame=0;frame<int(row.at("trace").size());++frame) {
                    CheckpointAdvance(w,frame);
                    if(picosha2::hash256_hex_string(w.checkpoint().dump())!=row.at("trace").at(frame).get<std::string>())
                        throw std::runtime_error("Fresh-process scenario "+std::to_string(i)+" diverged at "+std::to_string(frame));
                }
                Check(true,"Fresh-process scenario "+std::to_string(i)+" matches 110 frames");
            }
            std::cout<<Json{{"ok",true},{"checks",checks}}.dump()<<'\n'; return 0;
        }
        ShapeQueries(); ShapeOverlaps(); Drop(); Forces(); FilteringAndTriggers(); MaterialAndLifecycle(); Validation(); CheckpointBasics(); CheckpointRejection(); auto trace=Determinism();
        std::cout<<Json{{"ok",true},{"checks",checks},{"trace",trace}}.dump()<<'\n'; return 0;
    } catch(const std::exception& error) {
        std::cout<<Json{{"ok",false},{"checks",checks},{"error",error.what()}}.dump()<<'\n'; return 1;
    }
}
