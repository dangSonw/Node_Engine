#define GLM_ENABLE_EXPERIMENTAL
#include "runtime.hpp"
#include <glm/gtx/euler_angles.hpp>

namespace rt {
namespace {
void Require(bool ok,const char* why) { if(!ok) throw std::runtime_error(why); }
std::uint32_t Mask(std::int64_t n) { Require(n>=0&&n<=UINT32_MAX,"Physics mask must be 0..4294967295"); return std::uint32_t(n); }
bool Uniform(Vec3 s) { return std::abs(s.x-s.y)<=1e-9*std::max(s.x,s.y)&&std::abs(s.x-s.z)<=1e-9*std::max(s.x,s.z); }
PhysicsBody Desired(Ctx& c,const std::string& id,const PhysicsBinding& binding,PhysicsBody body) {
    for(auto e=EntityRef{id};!e.id.empty();e=GetParent(c,e)) {
        const auto scale=GetScale(c,e);
        Require(scale.x>0&&scale.y>0&&scale.z>0,"Rigid bodies require positive entity and ancestor scales");
        if(e.id!=id) Require(Uniform(scale),"Rigid-body ancestors require uniform scale");
    }
    auto matrix=GetWorldMatrix(c,{id});
    Vec3 scale(glm::length(Vec3(matrix[0])),glm::length(Vec3(matrix[1])),glm::length(Vec3(matrix[2])));
    Require(scale.x>0&&scale.y>0&&scale.z>0,"Rigid-body world scale is singular");
    if(body.shape!="box") Require(Uniform(scale),"Non-box colliders require uniform world scale");
    body.id=id; body.position=Vec3(matrix[3]);
    for(int i=0;i<3;++i) matrix[i]/=scale[i];
    body.rotation=glm::normalize(glm::quat_cast(glm::dmat3(matrix)));
    body.half_extents=binding.half_extents*scale;
    body.radius=binding.radius*scale.x; body.half_height=binding.half_height*scale.y;
    body.parts=binding.parts;
    for(auto& part:body.parts) {
        part.position*=scale.x; part.half_extents*=scale; part.radius*=scale.x; part.half_height*=scale.y;
        for(auto& vertex:part.vertices) vertex*=scale.x;
    }
    body.layer=std::uint32_t(GetEntityLayer(c,{id})); PhysicsWorld::validate(body);
    if(c.physics&&c.physics->has_character(id)) PhysicsWorld::validate_character(body,c.physics->character_settings(id));
    return body;
}
PhysicsWorld& Body(Ctx& c,EntityRef id) {
    SyncPhysics(c);
    Require(c.physics&&c.physics_scene.bodies.contains(id.id),"Entity has no rigid body"); return *c.physics;
}
void Add(Ctx& c,EntityRef id,PhysicsBody body,PhysicsBinding binding,const CharacterSettings* character=nullptr) {
    Require(EntityExists(c,id),"Rigid body requires a live scene entity");
    SyncPhysics(c); Require(!c.physics||!c.physics->contains(id.id),"Entity already has a rigid body");
    body=Desired(c,id.id,binding,body);
    if(character) PhysicsWorld::validate_character(body,*character);
    if(!c.physics) c.physics=std::make_shared<PhysicsWorld>();
    c.physics->add(body);
    c.physics->enabled(id.id,binding.enabled&&IsEntityActive(c,id));
    if(character) c.physics->attach_character(id.id,*character);
    binding.observed=GetWorldMatrix(c,id);
    c.physics_scene.bodies.emplace(id.id,binding);
}
Json MatrixJson(const glm::dmat4& matrix) {
    Json result=Json::array(); for(int col=0;col<4;++col) for(int row=0;row<4;++row) result.push_back(matrix[col][row]); return result;
}
CharacterSettings ReadCharacter(const Json& value) {
    Require(value.is_object()&&value.size()==4,"Character requires slope, step, floor snap and strength settings");
    return {FromJson<double>(value.at("max_slope")),FromJson<double>(value.at("step_height")),
        FromJson<double>(value.at("floor_snap")),FromJson<double>(value.at("max_strength"))};
}
}
PhysicsBody ReadAuthoredBody(const Json& j) {
    const std::size_t base=15+j.contains("character");
    Require(j.is_object()&&(j.size()==base||j.size()==base+1),"Rigid body requires all shape, motion and material settings");
    PhysicsBody b; b.id="authored";
    b.shape=FromJson<std::string>(j.at("shape")); b.motion=FromJson<std::string>(j.at("motion"));
    b.half_extents=FromJson<Vec3>(j.at("half_extents"));
    b.radius=FromJson<double>(j.at("radius")); b.half_height=FromJson<double>(j.at("half_height"));
    b.mass=FromJson<double>(j.at("mass")); b.friction=FromJson<double>(j.at("friction"));
    b.restitution=FromJson<double>(j.at("restitution")); b.gravity_scale=FromJson<double>(j.at("gravity_scale"));
    b.linear_damping=FromJson<double>(j.at("linear_damping")); b.angular_damping=FromJson<double>(j.at("angular_damping"));
    b.mask=Mask(FromJson<std::int64_t>(j.at("mask")));
    b.sensor=FromJson<bool>(j.at("sensor")); b.continuous=FromJson<bool>(j.at("continuous"));
    if(j.contains("parts")) { Require(j.at("parts").is_array(),"Rigid body parts must be an array"); for(const auto& part:j.at("parts")) {
        Require(part.is_object()&&part.size()==8,"Rigid body part requires shape, transform and geometry");
        PhysicsPart p; p.shape=FromJson<std::string>(part.at("shape")); p.position=FromJson<Vec3>(part.at("position"));
        const auto& q=part.at("rotation"); Require(q.is_array()&&q.size()==4,"Rigid body part rotation must have four values");
        p.rotation={FromJson<double>(q.at(0)),FromJson<double>(q.at(1)),FromJson<double>(q.at(2)),FromJson<double>(q.at(3))};
        p.half_extents=FromJson<Vec3>(part.at("half_extents")); p.radius=FromJson<double>(part.at("radius")); p.half_height=FromJson<double>(part.at("half_height"));
        Require(part.at("vertices").is_array()&&part.at("triangles").is_array(),"Rigid body mesh data must be arrays");
        for(const auto& vertex:part.at("vertices")) p.vertices.push_back(FromJson<Vec3>(vertex));
        for(const auto& triangle:part.at("triangles")) { Require(triangle.is_array()&&triangle.size()==3,"Rigid body triangle must have three indices"); p.triangles.push_back({std::uint32_t(triangle.at(0)),std::uint32_t(triangle.at(1)),std::uint32_t(triangle.at(2))}); }
        b.parts.push_back(std::move(p));
    } }
    (void)FromJson<bool>(j.at("enabled")); PhysicsWorld::validate(b);
    if(j.contains("character")) PhysicsWorld::validate_character(b,ReadCharacter(j.at("character")));
    return b;
}
void CreateAuthoredBody(Ctx& c,EntityRef id,const Json& j) {
    const auto body=ReadAuthoredBody(j);
    PhysicsBinding binding; binding.half_extents=body.half_extents; binding.radius=body.radius;
    binding.half_height=body.half_height; binding.parts=body.parts; binding.enabled=j.at("enabled").get<bool>();
    if(j.contains("character")) { const auto config=ReadCharacter(j.at("character")); Add(c,id,body,binding,&config); }
    else Add(c,id,body,binding);
}
void LoadAuthoredPhysics(Ctx& c) {
    for(const auto& entity:SceneEntities(c))
        if(entity.contains("rigid_body")&&!entity.at("rigid_body").is_null())
            CreateAuthoredBody(c,{entity.at("id").get<std::string>()},entity.at("rigid_body"));
}
void SyncPhysics(Ctx& c) {
    if(c.physics_scene.bodies.empty()) return;
    Require(bool(c.physics),"Scene physics is missing its native world");
    std::map<std::string,PhysicsBody> desired;
    for(const auto& [id,binding]:c.physics_scene.bodies) if(EntityExists(c,{id}))
        desired.emplace(id,Desired(c,id,binding,c.physics->settings(id)));
    for(auto it=c.physics_scene.bodies.begin();it!=c.physics_scene.bodies.end();) {
        if(!desired.contains(it->first)) { c.physics->remove(it->first); it=c.physics_scene.bodies.erase(it); }
        else ++it;
    }
    for(const auto& [id,body]:desired) {
        auto& binding=c.physics_scene.bodies.at(id); const auto before=c.physics->settings(id);
        c.physics->enabled(id,binding.enabled&&IsEntityActive(c,{id}));
        if(before.half_extents!=body.half_extents||before.radius!=body.radius||before.half_height!=body.half_height||before.parts!=body.parts) {
            if(c.physics->has_character(id)) Require(c.physics->reshape_character(id,body),"Character scale is obstructed");
            else c.physics->set_shape(id,body);
        }
        if(before.layer!=body.layer) c.physics->filter(id,body.layer,before.mask);
        const auto matrix=GetWorldMatrix(c,{id});
        if(matrix!=binding.observed) { c.physics->transform(id,body.position,body.rotation); binding.observed=matrix; }
    }
}
void ConfigureFixedUpdate(Ctx& c,const Json& program,std::function<void(Ctx&)> compiled) {
    const auto statements=program.at("events").value("fixed_update",Json::array());
    Require(statements.is_array(),"Fixed Update statements must be an array");
    if(statements.empty()) { c.fixed_update={}; return; }
    c.fixed_update=compiled?std::move(compiled):std::function<void(Ctx&)>([statements](Ctx& c){ Execute(c,statements); });
}
void AdvancePhysics(Ctx& c) {
    if(!c.physics&&!c.fixed_update) return;
    Require(!c.physics_advancing&&std::isfinite(c.dt)&&c.dt>=0&&c.dt<=1,"Physics frame delta must be 0..1 seconds outside simulation");
    struct Guard { Ctx& c; double dt; ~Guard(){c.dt=dt;c.physics_advancing=false;} } guard{c,c.dt};
    c.physics_advancing=true; SyncPhysics(c);
    c.physics_scene.remainder=finite(c.physics_scene.remainder+c.dt);
    while(c.physics_scene.remainder+1e-12>=FixedStep) {
        Require(c.physics_scene.ticks<UINT64_MAX,"Physics tick counter exhausted");
        c.dt=FixedStep;
        if(c.fixed_update) { c.fixed_update(c); DrainEvents(c); }
        SyncPhysics(c);
        if(c.physics) c.physics->step(FixedStep);
        std::vector<std::pair<int,std::string>> order;
        for(const auto& [id,binding]:c.physics_scene.bodies) {
            if(!binding.enabled||!IsEntityActive(c,{id})||c.physics->settings(id).motion=="static") continue;
            int depth=0; for(auto p=GetParent(c,{id});!p.id.empty();p=GetParent(c,p)) ++depth;
            order.emplace_back(depth,id);
        }
        std::sort(order.begin(),order.end());
        for(const auto& [_,id]:order) { const auto pose=c.physics->pose(id); SetPhysicsWorldPose(c,{id},pose.position,pose.rotation); }
        for(const auto& [_,id]:order) c.physics_scene.bodies.at(id).observed=GetWorldMatrix(c,{id});
        // Static children follow their newly simulated parents before the next query.
        SyncPhysics(c);
        c.physics_scene.remainder=std::max(0.,c.physics_scene.remainder-FixedStep); ++c.physics_scene.ticks;
        // Callbacks may remove bodies or mutate contact storage. Deliver a stable
        // batch after world poses are synchronized, outside Jolt callbacks.
        if(c.physics) {
            const auto contacts=c.physics->contacts();
            for(const auto& contact:contacts) { QueuePhysicsContact(c,contact); DrainEvents(c); }
            SyncPhysics(c);
        }
    }
}
void CreateBoxBody(Ctx& c,EntityRef id,Vec3 half,std::string motion,double mass,bool sensor,bool continuous) {
    PhysicsBody body; body.shape="box"; body.motion=motion; body.mass=mass; body.sensor=sensor; body.continuous=continuous;
    PhysicsBinding binding; binding.half_extents=half; Add(c,id,body,binding);
}
void CreateSphereBody(Ctx& c,EntityRef id,double radius,std::string motion,double mass,bool sensor,bool continuous) {
    PhysicsBody body; body.shape="sphere"; body.motion=motion; body.mass=mass; body.sensor=sensor; body.continuous=continuous;
    PhysicsBinding binding; binding.radius=radius; Add(c,id,body,binding);
}
void CreateCapsuleBody(Ctx& c,EntityRef id,double radius,double half_height,std::string motion,double mass,bool sensor,bool continuous) {
    PhysicsBody body; body.shape="capsule"; body.motion=motion; body.mass=mass; body.sensor=sensor; body.continuous=continuous;
    PhysicsBinding binding; binding.radius=radius; binding.half_height=half_height; Add(c,id,body,binding);
}
bool HasBody(Ctx& c,EntityRef id) { SyncPhysics(c); return c.physics_scene.bodies.contains(id.id); }
void RemoveBody(Ctx& c,EntityRef id) {
    SyncPhysics(c);
    if(c.physics_scene.bodies.contains(id.id)) { c.physics->remove(id.id); c.physics_scene.bodies.erase(id.id); }
}
void SetBodyType(Ctx& c,EntityRef id,std::string value) { Body(c,id).motion(id.id,value); }
std::string GetBodyType(Ctx& c,EntityRef id) { return Body(c,id).settings(id.id).motion; }
void SetBodyMass(Ctx& c,EntityRef id,double value) { Body(c,id).mass(id.id,value); }
double GetBodyMass(Ctx& c,EntityRef id) { return Body(c,id).settings(id.id).mass; }
void SetBodyVelocity(Ctx& c,EntityRef id,Vec3 value) { auto& world=Body(c,id); world.velocity(id.id,value,world.pose(id.id).angular_velocity); }
Vec3 GetBodyVelocity(Ctx& c,EntityRef id) { return Body(c,id).pose(id.id).velocity; }
void SetBodyAngularVelocity(Ctx& c,EntityRef id,Vec3 value) { auto& world=Body(c,id); world.velocity(id.id,world.pose(id.id).velocity,value); }
Vec3 GetBodyAngularVelocity(Ctx& c,EntityRef id) { return Body(c,id).pose(id.id).angular_velocity; }
void ApplyForce(Ctx& c,EntityRef id,Vec3 value) { Body(c,id).force(id.id,value); }
void ApplyTorque(Ctx& c,EntityRef id,Vec3 value) { Body(c,id).force(id.id,Vec3(0),value); }
void ApplyImpulse(Ctx& c,EntityRef id,Vec3 value) { Body(c,id).impulse(id.id,value); }
void SetBodyGravityScale(Ctx& c,EntityRef id,double value) { Body(c,id).gravity_scale(id.id,value); }
void SetBodyDamping(Ctx& c,EntityRef id,double linear,double angular) { Body(c,id).damping(id.id,linear,angular); }
void WakeBody(Ctx& c,EntityRef id) { Body(c,id).awake(id.id,true); }
void SleepBody(Ctx& c,EntityRef id) { Body(c,id).awake(id.id,false); }
bool IsBodyAwake(Ctx& c,EntityRef id) { return Body(c,id).pose(id.id).awake; }
void SetBodyEnabled(Ctx& c,EntityRef id,bool enabled) {
    auto& world=Body(c,id); world.enabled(id.id,enabled&&IsEntityActive(c,id)); c.physics_scene.bodies.at(id.id).enabled=enabled;
}
bool IsBodyEnabled(Ctx& c,EntityRef id) { (void)Body(c,id); return c.physics_scene.bodies.at(id.id).enabled&&IsEntityActive(c,id); }
void SetPhysicsMaterial(Ctx& c,EntityRef id,double friction,double restitution) { Body(c,id).material(id.id,friction,restitution); }
void SetCollisionMask(Ctx& c,EntityRef id,std::int64_t mask) { auto value=Mask(mask); auto& world=Body(c,id); world.filter(id.id,std::uint32_t(GetEntityLayer(c,id)),value); }
void IgnoreCollisionPair(Ctx& c,EntityRef a,EntityRef b,bool ignore) { auto& world=Body(c,a); (void)Body(c,b); world.ignore_pair(a.id,b.id,ignore); }
void SetPhysicsGravity(Ctx& c,Vec3 gravity) { if(!c.physics) c.physics=std::make_shared<PhysicsWorld>(gravity); else c.physics->gravity(gravity); }
EntityRef PhysicsRaycast(Ctx& c,Vec3 start,Vec3 displacement,std::int64_t mask,bool sensors,EntityRef exclude) {
    return std::get<1>(PhysicsRaycastHit(c,start,displacement,mask,sensors,exclude));
}
static PhysicsQueryResult QueryResult(const PhysicsHit& hit,Vec3 displacement) {
    return {hit.hit,EntityRef{hit.entity},hit.point,hit.normal,hit.fraction,glm::length(displacement)*hit.fraction};
}
PhysicsQueryResult PhysicsRaycastHit(Ctx& c,Vec3 start,Vec3 displacement,std::int64_t mask,bool sensors,EntityRef exclude) {
    const auto filter=Mask(mask); SyncPhysics(c);
    if(!c.physics) { PhysicsWorld empty; return QueryResult(empty.raycast(start,displacement,filter,sensors),displacement); }
    return QueryResult(c.physics->raycast(start,displacement,filter,sensors,exclude.id),displacement);
}
static PhysicsQueryResult ShapeCast(Ctx& c,PhysicsBody query,Vec3 rotation,Vec3 displacement,std::int64_t mask,bool sensors,EntityRef exclude) {
    const auto filter=Mask(mask); SyncPhysics(c); query.id="query";
    rotation=glm::radians(finite(rotation));
    query.rotation=glm::quat_cast(glm::eulerAngleYXZ(rotation.y,rotation.x,rotation.z));
    if(!c.physics) { PhysicsWorld empty; return QueryResult(empty.cast_shape(query,displacement,filter,sensors),displacement); }
    return QueryResult(c.physics->cast_shape(query,displacement,filter,sensors,exclude.id),displacement);
}
PhysicsQueryResult PhysicsSphereCast(Ctx& c,Vec3 origin,double radius,Vec3 displacement,std::int64_t mask,bool sensors,EntityRef exclude) {
    PhysicsBody query; query.shape="sphere"; query.position=origin; query.radius=radius;
    return ShapeCast(c,query,Vec3(0),displacement,mask,sensors,exclude);
}
PhysicsQueryResult PhysicsBoxCast(Ctx& c,Vec3 origin,Vec3 half,Vec3 rotation,Vec3 displacement,std::int64_t mask,bool sensors,EntityRef exclude) {
    PhysicsBody query; query.shape="box"; query.position=origin; query.half_extents=half;
    return ShapeCast(c,query,rotation,displacement,mask,sensors,exclude);
}
PhysicsQueryResult PhysicsCapsuleCast(Ctx& c,Vec3 origin,double radius,double half_height,Vec3 rotation,Vec3 displacement,std::int64_t mask,bool sensors,EntityRef exclude) {
    PhysicsBody query; query.shape="capsule"; query.position=origin; query.radius=radius; query.half_height=half_height;
    return ShapeCast(c,query,rotation,displacement,mask,sensors,exclude);
}
Array<EntityRef> PhysicsOverlapSphere(Ctx& c,Vec3 center,double radius,std::int64_t mask,bool sensors,EntityRef exclude) {
    const auto filter=Mask(mask); SyncPhysics(c); Array<EntityRef> result;
    if(!c.physics) { PhysicsWorld empty; (void)empty.overlap_sphere(center,radius,filter,sensors); return result; }
    for(const auto& id:c.physics->overlap_sphere(center,radius,filter,sensors,exclude.id)) result.push_back({id}); return result;
}
static Array<EntityRef> ShapeOverlap(Ctx& c,PhysicsBody query,Vec3 rotation,std::int64_t mask,bool sensors,EntityRef exclude) {
    const auto filter=Mask(mask); SyncPhysics(c); query.id="query";
    rotation=glm::radians(finite(rotation));
    query.rotation=glm::quat_cast(glm::eulerAngleYXZ(rotation.y,rotation.x,rotation.z));
    if(!c.physics) { PhysicsWorld empty; (void)empty.overlap_shape(query,filter,sensors); return {}; }
    Array<EntityRef> result;
    for(const auto& id:c.physics->overlap_shape(query,filter,sensors,exclude.id)) result.push_back({id});
    return result;
}
Array<EntityRef> PhysicsOverlapBox(Ctx& c,Vec3 center,Vec3 half,Vec3 rotation,std::int64_t mask,bool sensors,EntityRef exclude) {
    PhysicsBody query; query.shape="box"; query.position=center; query.half_extents=half;
    return ShapeOverlap(c,query,rotation,mask,sensors,exclude);
}
Array<EntityRef> PhysicsOverlapCapsule(Ctx& c,Vec3 center,double radius,double half_height,Vec3 rotation,std::int64_t mask,bool sensors,EntityRef exclude) {
    PhysicsBody query; query.shape="capsule"; query.position=center; query.radius=radius; query.half_height=half_height;
    return ShapeOverlap(c,query,rotation,mask,sensors,exclude);
}
void MoveKinematicBody(Ctx& c,EntityRef id,Vec3 position,Vec3 rotation,double seconds) {
    rotation=glm::radians(finite(rotation));
    Body(c,id).kinematic_target(id.id,position,glm::quat_cast(glm::eulerAngleYXZ(rotation.y,rotation.x,rotation.z)),seconds);
}
void CreateCharacter(Ctx& c,EntityRef id,double radius,double half_height,double mass,double slope,double step,double snap,double strength) {
    PhysicsBody body; body.shape="capsule"; body.motion="kinematic"; body.mass=mass;
    PhysicsBinding binding; binding.radius=radius; binding.half_height=half_height;
    const CharacterSettings config{slope,step,snap,strength}; Add(c,id,body,binding,&config);
}
bool HasCharacter(Ctx& c,EntityRef id) { SyncPhysics(c); return c.physics&&c.physics->has_character(id.id); }
void RemoveCharacter(Ctx& c,EntityRef id) { if(HasCharacter(c,id)) RemoveBody(c,id); }
void CharacterMove(Ctx& c,EntityRef id,Vec3 velocity) { Body(c,id).character_move(id.id,velocity); }
bool CharacterJump(Ctx& c,EntityRef id,double speed) { return Body(c,id).character_jump(id.id,speed); }
void ConfigureCharacter(Ctx& c,EntityRef id,double slope,double step,double snap,double strength) {
    Body(c,id).configure_character(id.id,{slope,step,snap,strength});
}
bool CharacterResize(Ctx& c,EntityRef id,double radius,double half_height) {
    auto& world=Body(c,id); auto binding=c.physics_scene.bodies.at(id.id);
    binding.radius=radius; binding.half_height=half_height;
    const auto next=Desired(c,id.id,binding,world.settings(id.id));
    if(!world.character_resize(id.id,next.radius,next.half_height)) return false;
    const auto pose=world.pose(id.id); SetPhysicsWorldPose(c,id,pose.position,pose.rotation);
    binding.observed=GetWorldMatrix(c,id); c.physics_scene.bodies.at(id.id)=binding;
    return true;
}
CharacterGroundResult CharacterGroundCheck(Ctx& c,EntityRef id) {
    const auto state=Body(c,id).character_state(id.id);
    return {state.grounded,state.ground_state,EntityRef{state.ground_entity},state.ground_point,state.ground_normal,state.ground_velocity};
}
void CheckPhysicsClone(Ctx& c,EntityRef id) {
    SyncPhysics(c);
    if(c.physics_scene.bodies.contains(id.id)) Require(c.physics->size()<PhysicsWorld::MaxBodies,"Physics world exceeds 4096 bodies");
}
void ClonePhysics(Ctx& c,EntityRef source,EntityRef target) {
    if(!c.physics_scene.bodies.contains(source.id)) return;
    auto body=c.physics->settings(source.id); auto pose=c.physics->pose(source.id);
    const bool character=c.physics->has_character(source.id);
    body.velocity=character?Vec3(0):pose.velocity; body.angular_velocity=pose.angular_velocity;
    Add(c,target,body,c.physics_scene.bodies.at(source.id));
    if(character) c.physics->clone_character(source.id,target.id);
    else if(!pose.awake) c.physics->awake(target.id,false);
}
Json PhysicsSnapshot(const Ctx& c) {
    if(!c.physics&&!c.fixed_update) return nullptr;
    Json bodies=Json::object();
    for(const auto& [id,binding]:c.physics_scene.bodies) {
        if(!EntityExists(c,{id})) continue;
        const auto pose=c.physics->pose(id); const auto body=c.physics->settings(id);
        bodies[id]={{"position",ToJson(pose.position)},{"rotation",{pose.rotation.w,pose.rotation.x,pose.rotation.y,pose.rotation.z}},
            {"velocity",ToJson(pose.velocity)},{"angular_velocity",ToJson(pose.angular_velocity)},
            {"awake",pose.awake},{"enabled",binding.enabled&&IsEntityActive(c,{id})},{"motion",body.motion},{"shape",body.shape},{"mass",body.mass}};
        if(c.physics->has_character(id)) {
            const auto state=c.physics->character_state(id); const auto config=c.physics->character_settings(id);
            bodies[id]["character"]={{"grounded",state.grounded},{"ground_state",state.ground_state},{"ground_entity",state.ground_entity},
                {"ground_point",ToJson(state.ground_point)},{"ground_normal",ToJson(state.ground_normal)},{"ground_velocity",ToJson(state.ground_velocity)},
                {"radius",body.radius},{"half_height",body.half_height},{"max_slope",config.max_slope},{"step_height",config.step_height},
                {"floor_snap",config.floor_snap},{"max_strength",config.max_strength}};
        }
    }
    return {{"ticks",c.physics_scene.ticks},{"remainder",c.physics_scene.remainder},{"bodies",bodies}};
}
Json PhysicsStateCheckpoint(const Ctx& c) {
    Require(!c.physics_advancing,"Physics checkpoint requires a simulation boundary");
    if(!c.physics&&c.physics_scene.ticks==0&&c.physics_scene.remainder==0) return nullptr;
    Json bindings=Json::object();
    for(const auto& [id,b]:c.physics_scene.bodies) {
        Require(EntityExists(c,{id})&&c.physics&&c.physics->contains(id),"Physics checkpoint has a stale entity binding");
        bindings[id]={{"half_extents",ToJson(b.half_extents)},{"radius",b.radius},{"half_height",b.half_height},{"enabled",b.enabled},{"observed",MatrixJson(b.observed)}};
        if(!b.parts.empty()) { bindings[id]["parts"]=Json::array(); for(const auto& part:b.parts) {
            Json vertices=Json::array(),triangles=Json::array(); for(const auto& v:part.vertices) vertices.push_back(ToJson(v)); for(const auto& t:part.triangles) triangles.push_back({t[0],t[1],t[2]});
            bindings[id]["parts"].push_back({{"shape",part.shape},{"position",ToJson(part.position)},{"rotation",{part.rotation.w,part.rotation.x,part.rotation.y,part.rotation.z}},{"half_extents",ToJson(part.half_extents)},{"radius",part.radius},{"half_height",part.half_height},{"vertices",vertices},{"triangles",triangles}});
        } }
    }
    return {{"version",1},{"world",c.physics?c.physics->checkpoint():Json()},{"bindings",bindings},
        {"remainder",c.physics_scene.remainder},{"ticks",c.physics_scene.ticks}};
}
void RestorePhysicsState(Ctx& c,const Json& saved) {
    c.physics.reset(); c.physics_scene={};
    if(saved.is_null()) return;
    Require(saved.is_object()&&saved.size()==5&&saved.at("version").is_number_integer()&&saved.at("version")==1,"Invalid scene physics checkpoint");
    const auto remainder=FromJson<double>(saved.at("remainder"));
    Require(remainder>=0&&remainder<FixedStep,"Invalid physics accumulator");
    const auto& ticks=saved.at("ticks");
    Require(ticks.is_number_integer()&&(ticks.is_number_unsigned()||ticks.get<std::int64_t>()>=0)&&ticks.get<std::uint64_t>()<UINT64_MAX,"Invalid physics tick counter");
    if(!saved.at("world").is_null()) { c.physics=std::make_shared<PhysicsWorld>(); c.physics->restore(saved.at("world")); }
    c.physics_scene.remainder=remainder; c.physics_scene.ticks=ticks.get<std::uint64_t>();
    const auto& bindings=saved.at("bindings"); Require(bindings.is_object()&&bindings.size()<=PhysicsWorld::MaxBodies,"Invalid physics bindings");
    for(const auto& [id,row]:bindings.items()) {
        Require(EntityExists(c,{id})&&c.physics&&c.physics->contains(id),"Physics binding requires a live entity and body");
        Require(row.is_object()&&(row.size()==5||row.size()==6),"Invalid physics binding fields"); PhysicsBinding b;
        b.half_extents=FromJson<Vec3>(row.at("half_extents")); b.radius=FromJson<double>(row.at("radius"));
        b.half_height=FromJson<double>(row.at("half_height")); b.enabled=FromJson<bool>(row.at("enabled"));
        if(row.contains("parts")) { Require(row.at("parts").is_array(),"Invalid physics binding parts"); for(const auto& part:row.at("parts")) {
            Require(part.is_object()&&part.size()==8,"Invalid physics binding part"); PhysicsPart value; value.shape=FromJson<std::string>(part.at("shape")); value.position=FromJson<Vec3>(part.at("position"));
            const auto& q=part.at("rotation"); Require(q.is_array()&&q.size()==4,"Invalid physics binding part rotation"); value.rotation={FromJson<double>(q.at(0)),FromJson<double>(q.at(1)),FromJson<double>(q.at(2)),FromJson<double>(q.at(3))}; value.half_extents=FromJson<Vec3>(part.at("half_extents")); value.radius=FromJson<double>(part.at("radius")); value.half_height=FromJson<double>(part.at("half_height"));
            for(const auto& v:part.at("vertices")) value.vertices.push_back(FromJson<Vec3>(v)); for(const auto& t:part.at("triangles")) { Require(t.is_array()&&t.size()==3,"Invalid physics binding triangle"); value.triangles.push_back({std::uint32_t(t.at(0)),std::uint32_t(t.at(1)),std::uint32_t(t.at(2))}); } b.parts.push_back(std::move(value));
        } }
        const auto& matrix=row.at("observed"); Require(matrix.is_array()&&matrix.size()==16,"Invalid observed physics transform");
        for(int col=0;col<4;++col) for(int r=0;r<4;++r) b.observed[col][r]=FromJson<double>(matrix.at(col*4+r));
        const auto actual=c.physics->settings(id); const auto expected=Desired(c,id,b,actual);
        if(c.physics->has_character(id)) {
            const auto close=[](double a,double z){return std::abs(a-z)<=1e-9*std::max({1.,std::abs(a),std::abs(z)});};
            Require(close(expected.radius,actual.radius)&&close(expected.half_height,actual.half_height)&&
                b.observed==GetWorldMatrix(c,{id}),"Character checkpoint disagrees with scene dimensions or transform");
            const auto pose=c.physics->pose(id);
            Require(glm::length(pose.position-expected.position)<=1e-6+1e-9*glm::length(expected.position)&&
                std::abs(glm::dot(pose.rotation,expected.rotation))>1-1e-8,
                "Character checkpoint pose disagrees with scene");
            Require((c.physics->character_state(id).ground_state!="disabled")==
                (b.enabled&&IsEntityActive(c,{id})),"Character checkpoint activity disagrees with scene");
        }
        c.physics_scene.bodies.emplace(id,b);
    }
    Require(PhysicsStateCheckpoint(c)==saved,"Physics scene cannot be restored exactly");
}
}
