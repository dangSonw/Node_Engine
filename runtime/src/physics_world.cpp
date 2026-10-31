#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Character/CharacterVirtual.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <Jolt/Physics/Collision/Shape/MutableCompoundShape.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/ShapeCast.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/TransformedShape.h>
#include "physics_world.hpp"
#include "physics_checkpoint_codec.hpp"
#include <array>
#include <set>

namespace rt {
namespace {
// Bound inputs before converting to Jolt's single precision velocities/shapes.
double Range(double v,double low,double high,const char* name) {
    if(!std::isfinite(v)||v<low||v>high) throw std::runtime_error(std::string("Physics ")+name+" out of range");
    return v;
}
Vec3 Range(Vec3 v,double max,const char* name) {
    Range(v.x,-max,max,name); Range(v.y,-max,max,name); Range(v.z,-max,max,name); return v;
}
JPH::Vec3 Vector(Vec3 v) { return {float(v.x),float(v.y),float(v.z)}; }
JPH::RVec3 Position(Vec3 v) { Range(v,1e9,"position"); return {v.x,v.y,v.z}; }
template<class T> Vec3 Vector(T v) { return {v.GetX(),v.GetY(),v.GetZ()}; }
JPH::Quat Rotation(glm::dquat q) {
    Range(Vec3(q.x,q.y,q.z),1e6,"rotation"); Range(q.w,-1e6,1e6,"rotation");
    const double length=glm::length(q);
    if(length<1e-12) throw std::runtime_error("Physics rotation must be nonzero");
    q/=length; return JPH::Quat(float(q.x),float(q.y),float(q.z),float(q.w)).Normalized();
}
JPH::EMotionType Motion(const std::string& value) {
    if(value=="static") return JPH::EMotionType::Static;
    if(value=="kinematic") return JPH::EMotionType::Kinematic;
    if(value=="dynamic") return JPH::EMotionType::Dynamic;
    throw std::runtime_error("Physics motion must be static, kinematic or dynamic");
}
JPH::ShapeSettings::ShapeResult MakeShape(const PhysicsPart& part) {
    if(part.shape=="box")
        return JPH::BoxShapeSettings(Vector(part.half_extents),float(std::min({.05,part.half_extents.x*.1,part.half_extents.y*.1,part.half_extents.z*.1}))).Create();
    if(part.shape=="sphere") return JPH::SphereShapeSettings(float(part.radius)).Create();
    if(part.shape=="capsule") return JPH::CapsuleShapeSettings(float(part.half_height),float(part.radius)).Create();
    if(part.shape=="mesh") {
        JPH::VertexList vertices;
        JPH::IndexedTriangleList triangles;
        vertices.reserve(part.vertices.size()); triangles.reserve(part.triangles.size());
        for(const auto& v:part.vertices) vertices.push_back(JPH::Float3(float(v.x),float(v.y),float(v.z)));
        for(const auto& t:part.triangles) triangles.emplace_back(t[0],t[1],t[2]);
        return JPH::MeshShapeSettings(std::move(vertices),std::move(triangles)).Create();
    }
    throw std::runtime_error("Unknown physics part shape: "+part.shape);
}
JPH::ShapeSettings::ShapeResult MakeShape(const PhysicsBody& body) {
    if(body.shape=="box"||body.shape=="sphere"||body.shape=="capsule") {
        PhysicsPart part; part.shape=body.shape; part.half_extents=body.half_extents;
        part.radius=body.radius; part.half_height=body.half_height; return MakeShape(part);
    }
    if(body.shape=="mesh") {
        if(body.parts.size()!=1) throw std::runtime_error("Mesh body requires exactly one mesh part");
        return MakeShape(body.parts.front());
    }
    JPH::MutableCompoundShapeSettings settings;
    for(const auto& part:body.parts) {
        auto child=MakeShape(part);
        if(child.HasError()) return child;
        settings.AddShape(Vector(part.position),Rotation(part.rotation),child.Get());
    }
    return settings.Create();
}
JPH::RefConst<JPH::Shape> QueryShape(const PhysicsBody& query) {
    PhysicsWorld::validate(query);
    auto result=MakeShape(query);
    if(result.HasError()) throw std::runtime_error("Invalid physics shape: "+std::string(result.GetError().c_str()));
    return result.Get();
}
void ValidateCharacterSettings(const CharacterSettings& settings) {
    Range(settings.max_slope,1,89,"character slope angle");
    Range(settings.step_height,0,100,"character step height");
    Range(settings.floor_snap,0,100,"character floor snap");
    Range(settings.max_strength,0,1e9,"character strength");
}
void Upright(JPH::Quat rotation) {
    if((rotation.RotateAxisY()-JPH::Vec3::sAxisY()).LengthSq()>1e-8f)
        throw std::runtime_error("Character capsule must stay upright");
}
struct JoltLifetime {
    JoltLifetime() {
        JPH::RegisterDefaultAllocator(); JPH::Factory::sInstance=new JPH::Factory(); JPH::RegisterTypes();
    }
    ~JoltLifetime() { JPH::UnregisterTypes(); delete JPH::Factory::sInstance; JPH::Factory::sInstance=nullptr; }
};
struct BroadLayers final : JPH::BroadPhaseLayerInterface {
    JPH::uint GetNumBroadPhaseLayers() const override { return 2; }
    JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer layer) const override { return JPH::BroadPhaseLayer(layer); }
#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
    const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer layer) const override {
        return layer==JPH::BroadPhaseLayer(0)?"Static":"Moving";
    }
#endif
};
struct BroadFilter final : JPH::ObjectVsBroadPhaseLayerFilter {
    bool ShouldCollide(JPH::ObjectLayer a,JPH::BroadPhaseLayer b) const override { return a!=0||b==JPH::BroadPhaseLayer(1); }
};
struct LayerFilter final : JPH::ObjectLayerPairFilter {
    bool ShouldCollide(JPH::ObjectLayer a,JPH::ObjectLayer b) const override { return a!=0||b!=0; }
};
struct MaskFilter final : JPH::GroupFilter {
    bool CanCollide(const JPH::CollisionGroup& a,const JPH::CollisionGroup& b) const override {
        return (a.GetGroupID()&b.GetSubGroupID())&&(b.GetGroupID()&a.GetSubGroupID());
    }
};
struct QueryFilter final : JPH::BodyFilter {
    std::uint32_t mask; bool sensors; JPH::BodyID exclude;
    QueryFilter(std::uint32_t m,bool s,JPH::BodyID e):mask(m),sensors(s),exclude(e) {}
    bool ShouldCollide(const JPH::BodyID& id) const override { return id!=exclude; }
    bool ShouldCollideLocked(const JPH::Body& b) const override {
        return (mask&b.GetCollisionGroup().GetGroupID())&&(sensors||!b.IsSensor());
    }
};
using Pair=std::pair<std::string,std::string>;
using BodyPair=std::pair<std::uint32_t,std::uint32_t>;
Pair Ordered(std::string a,std::string b) { if(a>b) std::swap(a,b); return {std::move(a),std::move(b)}; }
}

struct PhysicsWorld::Impl final : JPH::ContactListener {
    struct Entry { JPH::BodyID body; PhysicsBody settings; bool enabled=true; };
    struct Character {
        JPH::Ref<JPH::CharacterVirtual> controller;
        CharacterSettings settings;
        Vec3 desired{0};
        double jump=0;
    };
    BroadLayers layers;
    BroadFilter broad_filter;
    LayerFilter layer_filter;
    JPH::Ref<MaskFilter> masks=new MaskFilter();
    JPH::TempAllocatorMalloc allocator;
    JPH::JobSystemSingleThreaded jobs{JPH::cMaxPhysicsJobs};
    JPH::PhysicsSystem world;
    std::map<std::string,Entry> bodies;
    std::map<std::uint32_t,std::string> names;
    std::array<std::uint8_t,MaxBodies> generations{};
    std::array<bool,MaxBodies> occupied{};
    std::set<std::uint32_t> retired;
    std::set<Pair> ignored;
    // Only primitive convex shapes are accepted, hence one subshape pair per body pair.
    std::map<BodyPair,PhysicsContact> touching;
    std::set<BodyPair> dormant;
    std::vector<PhysicsContact> events;
    std::map<std::string,Character> characters;
    explicit Impl(Vec3 gravity) {
        world.Init(MaxBodies,0,16384,16384,layers,broad_filter,layer_filter);
        world.SetGravity(Vector(Range(gravity,1e5,"gravity"))); world.SetContactListener(this);
    }
    ~Impl() {
        characters.clear();
        world.SetContactListener(nullptr);
        auto& api=world.GetBodyInterface();
        for(const auto& [_,entry]:bodies) {
            if(entry.enabled) api.RemoveBody(entry.body);
            api.DestroyBody(entry.body);
        }
    }
    Entry& get(const std::string& id) {
        auto found=bodies.find(id);
        if(found==bodies.end()) throw std::runtime_error("Physics body does not exist: "+id);
        return found->second;
    }
    Character& character(const std::string& id) {
        auto found=characters.find(id);
        if(found==characters.end()) throw std::runtime_error("Entity has no character controller: "+id);
        return found->second;
    }
    struct CharacterFilter final : JPH::BodyFilter {
        const Impl& owner; const Entry& source;
        CharacterFilter(const Impl& o,const Entry& s):owner(o),source(s) {}
        bool ShouldCollide(const JPH::BodyID& id) const override {
            auto it=owner.names.find(id.GetIndexAndSequenceNumber());
            return id!=source.body&&it!=owner.names.end()&&!owner.ignored.contains(Ordered(source.settings.id,it->second));
        }
        bool ShouldCollideLocked(const JPH::Body& body) const override {
            const auto& group=body.GetCollisionGroup();
            return !body.IsSensor()&&(source.settings.mask&group.GetGroupID())&&((1u<<source.settings.layer)&group.GetSubGroupID());
        }
    };
    void refresh_character(const std::string& id) {
        character(id).controller->RefreshContacts({},{},CharacterFilter(*this,get(id)),{},allocator);
    }
    bool ground_available(const Entry& body,const Character& c) const {
        const auto ground=c.controller->GetGroundBodyID();
        if(!body.enabled||!names.contains(ground.GetIndexAndSequenceNumber())||!world.GetBodyInterface().IsAdded(ground)) return false;
        const CharacterFilter filter(*this,body); JPH::BodyLockRead lock(world.GetBodyLockInterface(),ground);
        return lock.Succeeded()&&filter.ShouldCollide(ground)&&filter.ShouldCollideLocked(lock.GetBody());
    }
    bool grounded(const Entry& body,const Character& c) const {
        return c.controller->GetGroundState()==JPH::CharacterBase::EGroundState::OnGround&&ground_available(body,c);
    }
    void advance_characters(double seconds) {
        auto& api=world.GetBodyInterface();
        for(auto& [id,c]:characters) {
            auto& body=get(id); if(!body.enabled) continue;
            auto& controller=*c.controller; controller.UpdateGroundVelocity();
            const auto gravity=world.GetGravity()*float(body.settings.gravity_scale);
            auto velocity=controller.GetLinearVelocity();
            const auto ground_velocity=controller.GetGroundVelocity();
            if(grounded(body,c)&&velocity.GetY()-ground_velocity.GetY()<.1f) {
                velocity=ground_velocity;
                if(c.jump>0) velocity+=JPH::Vec3(0,float(c.jump),0);
            } else velocity=JPH::Vec3(0,velocity.GetY(),0);
            c.jump=0;
            velocity+=Vector(c.desired)+gravity*float(seconds);
            velocity=JPH::Vec3::sMin(JPH::Vec3::sMax(velocity,JPH::Vec3::sReplicate(-10000)),JPH::Vec3::sReplicate(10000));
            controller.SetLinearVelocity(controller.CancelVelocityTowardsSteepSlopes(velocity));
            JPH::CharacterVirtual::ExtendedUpdateSettings settings;
            settings.mStickToFloorStepDown={0,-float(c.settings.floor_snap),0};
            settings.mWalkStairsStepUp={0,float(c.settings.step_height),0};
            controller.ExtendedUpdate(float(seconds),gravity,settings,{},{},CharacterFilter(*this,body),{},allocator);
            // Mirror Jolt's inner-body behavior using our own stable body allocation.
            api.SetPositionAndRotation(body.body,controller.GetPosition(),controller.GetRotation(),JPH::EActivation::Activate);
        }
    }
    JPH::BodyID excluded(const std::string& id) const {
        auto found=bodies.find(id); return found==bodies.end()?JPH::BodyID():found->second.body;
    }
    void dynamic(const Entry& e) {
        if(e.settings.motion!="dynamic"||!e.enabled) throw std::runtime_error("Physics operation needs an enabled dynamic body");
    }
    JPH::EActivation activation(const Entry& e,bool wake=true) const {
        return wake&&e.enabled&&e.settings.motion!="static"?JPH::EActivation::Activate:JPH::EActivation::DontActivate;
    }
    void changed(Entry& e) {
        world.GetBodyInterface().InvalidateContactCache(e.body);
        if(activation(e)==JPH::EActivation::Activate) world.GetBodyInterface().ActivateBody(e.body);
        auto bounds=world.GetBodyInterface().GetTransformedShape(e.body).GetWorldSpaceBounds();
        bounds.ExpandBy(JPH::Vec3::sReplicate(world.GetPhysicsSettings().mSpeculativeContactDistance));
        world.GetBodyInterface().ActivateBodiesInAABox(bounds,{},{});
    }
    bool sleeping_contact(BodyPair pair,PhysicsContact& contact) {
        auto& api=world.GetBodyInterface(); const JPH::BodyID a(pair.first),b(pair.second);
        if(!names.contains(pair.first)||!names.contains(pair.second)||!api.IsAdded(a)||!api.IsAdded(b)||api.IsActive(a)||api.IsActive(b)) return false;
        if(api.GetMotionType(a)==JPH::EMotionType::Static&&api.GetMotionType(b)==JPH::EMotionType::Static) return false;
        if(!masks->CanCollide(api.GetCollisionGroup(a),api.GetCollisionGroup(b))||ignored.contains({contact.first,contact.second})) return false;
        auto first=api.GetTransformedShape(a),second=api.GetTransformedShape(b);
        JPH::ClosestHitCollisionCollector<JPH::CollideShapeCollector> collector;
        JPH::CollideShapeSettings settings; settings.mMaxSeparationDistance=world.GetPhysicsSettings().mSpeculativeContactDistance;
        second.CollideShape(first.mShape,first.GetShapeScale(),first.GetCenterOfMassTransform(),settings,first.mShapePositionCOM,collector);
        if(!collector.HadHit()) return false;
        contact.point=Vector(first.mShapePositionCOM+collector.mHit.mContactPointOn1);
        contact.normal=Vector(collector.mHit.mPenetrationAxis.NormalizedOr(JPH::Vec3::sAxisY()));
        if(contact.first!=names.at(pair.first)) contact.normal=-contact.normal;
        return true;
    }
    JPH::ValidateResult OnContactValidate(const JPH::Body& a,const JPH::Body& b,JPH::RVec3Arg,const JPH::CollideShapeResult&) override {
        return ignored.contains(Ordered(names.at(a.GetID().GetIndexAndSequenceNumber()),names.at(b.GetID().GetIndexAndSequenceNumber())))
            ?JPH::ValidateResult::RejectAllContactsForThisBodyPair:JPH::ValidateResult::AcceptAllContactsForThisBodyPair;
    }
    void contact(const JPH::Body& a,const JPH::Body& b,const JPH::ContactManifold& manifold) {
        auto first=names.at(a.GetID().GetIndexAndSequenceNumber()), second=names.at(b.GetID().GetIndexAndSequenceNumber());
        Vec3 normal=Vector(manifold.mWorldSpaceNormal);
        if(first>second) { std::swap(first,second); normal=-normal; }
        Vec3 point=manifold.mRelativeContactPointsOn1.empty()?Vector(manifold.mBaseOffset):Vector(manifold.GetWorldSpaceContactPointOn1(0));
        touching[{a.GetID().GetIndexAndSequenceNumber(),b.GetID().GetIndexAndSequenceNumber()}]={first,second,"",point,normal,a.IsSensor()||b.IsSensor()};
    }
    void OnContactAdded(const JPH::Body& a,const JPH::Body& b,const JPH::ContactManifold& m,JPH::ContactSettings&) override { contact(a,b,m); }
    void OnContactPersisted(const JPH::Body& a,const JPH::Body& b,const JPH::ContactManifold& m,JPH::ContactSettings&) override { contact(a,b,m); }
    void OnContactRemoved(const JPH::SubShapeIDPair& pair) override {
        touching.erase({pair.GetBody1ID().GetIndexAndSequenceNumber(),pair.GetBody2ID().GetIndexAndSequenceNumber()});
    }
};

PhysicsWorld::PhysicsWorld(Vec3 gravity) {
    static JoltLifetime jolt;
    impl=std::make_unique<Impl>(gravity);
}
PhysicsWorld::~PhysicsWorld()=default;
void PhysicsWorld::add(const PhysicsBody& p) {
    // Own allocation order so fresh-process restoration preserves future BodyIDs.
    for(std::uint32_t slot=0;slot<MaxBodies;++slot) if(!impl->occupied[slot]) {
        for(unsigned offset=1;offset<=256;++offset) {
            auto sequence=std::uint8_t(impl->generations[slot]+offset);
            auto id=JPH::BodyID(slot,sequence).GetIndexAndSequenceNumber();
            if(impl->retired.contains(id)) continue;
            add_with_id(p,id); return;
        }
    }
    throw std::runtime_error("Physics body capacity exhausted; step before reusing retired IDs");
}
void PhysicsWorld::add_with_id(const PhysicsBody& p,std::uint32_t native_id,bool activate) {
    validate(p);
    if(p.id.empty()||p.id.size()>1024) throw std::runtime_error("Physics body ID must contain 1..1024 bytes");
    if(contains(p.id)) throw std::runtime_error("Physics body already exists: "+p.id);
    if(size()>=MaxBodies) throw std::runtime_error("Physics world exceeds 4096 bodies");
    auto motion=Motion(p.motion);
    auto position=Position(p.position); auto rotation=Rotation(p.rotation);
    auto result=MakeShape(p);
    if(result.HasError()) throw std::runtime_error("Invalid physics shape: "+std::string(result.GetError().c_str()));
    JPH::BodyCreationSettings settings(result.Get(),position,rotation,motion,motion==JPH::EMotionType::Static?0:1);
    settings.mAllowDynamicOrKinematic=true;
    settings.mLinearVelocity=Vector(p.velocity); settings.mAngularVelocity=Vector(p.angular_velocity);
    settings.mFriction=float(p.friction); settings.mRestitution=float(p.restitution);
    settings.mGravityFactor=float(p.gravity_scale); settings.mLinearDamping=float(p.linear_damping); settings.mAngularDamping=float(p.angular_damping);
    settings.mIsSensor=p.sensor; settings.mCollideKinematicVsNonDynamic=p.sensor;
    settings.mMotionQuality=p.continuous?JPH::EMotionQuality::LinearCast:JPH::EMotionQuality::Discrete;
    settings.mOverrideMassProperties=JPH::EOverrideMassProperties::CalculateInertia; settings.mMassPropertiesOverride.mMass=float(p.mass);
    settings.mCollisionGroup=JPH::CollisionGroup(impl->masks,1u<<p.layer,p.mask);
    auto& api=impl->world.GetBodyInterface();
    auto* body=api.CreateBodyWithID(JPH::BodyID(native_id),settings);
    if(!body) throw std::runtime_error("Cannot allocate physics body");
    auto id=body->GetID();
    try { impl->bodies.emplace(p.id,Impl::Entry{id,p}); impl->names.emplace(id.GetIndexAndSequenceNumber(),p.id); }
    catch(...) { impl->bodies.erase(p.id); impl->names.erase(id.GetIndexAndSequenceNumber()); api.DestroyBody(id); throw; }
    impl->occupied[id.GetIndex()]=true; impl->generations[id.GetIndex()]=id.GetSequenceNumber();
    api.AddBody(id,!activate||motion==JPH::EMotionType::Static?JPH::EActivation::DontActivate:JPH::EActivation::Activate);
}
void PhysicsWorld::validate(const PhysicsBody& p) {
    if(p.id.empty()||p.id.size()>1024) throw std::runtime_error("Physics body ID must contain 1..1024 bytes");
    (void)Motion(p.motion); (void)Position(p.position); (void)Rotation(p.rotation);
    Range(p.half_extents.x,.001,1e5,"box half extent"); Range(p.half_extents.y,.001,1e5,"box half extent"); Range(p.half_extents.z,.001,1e5,"box half extent");
    Range(p.radius,.001,1e5,"radius"); Range(p.half_height,.001,1e5,"capsule half height");
    Range(p.mass,.001,1e9,"mass"); Range(p.friction,0,10,"friction"); Range(p.restitution,0,1,"restitution");
    Range(p.gravity_scale,-1000,1000,"gravity scale");
    Range(p.linear_damping,0,1000,"linear damping"); Range(p.angular_damping,0,1000,"angular damping");
    Range(p.velocity,1e4,"velocity"); Range(p.angular_velocity,1e4,"angular velocity");
    if(p.layer>31) throw std::runtime_error("Physics layer must be 0..31");
    if(p.shape!="box"&&p.shape!="sphere"&&p.shape!="capsule"&&p.shape!="compound"&&p.shape!="mesh") throw std::runtime_error("Physics shape must be box, sphere, capsule, compound or mesh");
    if((p.shape=="compound"||p.shape=="mesh") && (p.parts.empty()||p.parts.size()>256)) throw std::runtime_error("Compound/mesh physics shape requires 1..256 parts");
    if(p.shape=="mesh" && p.motion!="static") throw std::runtime_error("Mesh physics bodies must be static");
    if(p.shape=="compound" && p.parts.empty()) throw std::runtime_error("Compound physics shape requires at least one part");
    for(const auto& part:p.parts) {
        if(part.shape!="box"&&part.shape!="sphere"&&part.shape!="capsule"&&part.shape!="mesh") throw std::runtime_error("Physics part shape is invalid");
        Range(part.position,1e9,"part position"); (void)Rotation(part.rotation);
        Range(part.half_extents.x,.001,1e5,"part box half extent"); Range(part.half_extents.y,.001,1e5,"part box half extent"); Range(part.half_extents.z,.001,1e5,"part box half extent");
        Range(part.radius,.001,1e5,"part radius"); Range(part.half_height,.001,1e5,"part capsule half height");
        if(part.shape=="mesh") {
            if(part.vertices.size()<3||part.vertices.size()>1000000||part.triangles.empty()||part.triangles.size()>1000000) throw std::runtime_error("Mesh collider vertices/triangles are out of range");
            for(const auto& v:part.vertices) Range(v,1e6,"mesh vertex");
            for(const auto& t:part.triangles) for(auto index:t) if(index>=part.vertices.size()) throw std::runtime_error("Mesh collider triangle index is out of range");
        } else if(p.shape=="mesh") throw std::runtime_error("Mesh body parts must have mesh shape");
    }
    if(p.shape=="compound" && p.motion!="static") for(const auto& part:p.parts) if(part.shape=="mesh") throw std::runtime_error("Compound bodies containing mesh parts must be static");
}
PhysicsBody PhysicsWorld::settings(const std::string& id) const { return impl->get(id).settings; }
void PhysicsWorld::shape(const std::string& id,Vec3 half_extents,double radius,double half_height) {
    if(has_character(id)) throw std::runtime_error("Resize a character through character_resize");
    auto p=settings(id); p.half_extents=half_extents; p.radius=radius; p.half_height=half_height; validate(p);
    set_shape(id,p);
}
void PhysicsWorld::set_shape(const std::string& id,const PhysicsBody& desired) {
    if(has_character(id)) throw std::runtime_error("Resize a character through character_resize");
    auto p=settings(id); p.shape=desired.shape; p.half_extents=desired.half_extents; p.radius=desired.radius; p.half_height=desired.half_height; p.parts=desired.parts; validate(p);
    auto result=MakeShape(p);
    if(result.HasError()) throw std::runtime_error("Invalid physics shape: "+std::string(result.GetError().c_str()));
    auto& e=impl->get(id);
    auto& api=impl->world.GetBodyInterface();
    api.SetShape(e.body,result.Get(),false,JPH::EActivation::DontActivate);
    e.settings=p; mass(id,p.mass); impl->changed(e);
}
void PhysicsWorld::remove(const std::string& id) {
    auto entry=impl->get(id); auto& api=impl->world.GetBodyInterface();
    if(impl->retired.size()>=MaxCollection) throw std::runtime_error("Step physics before removing more bodies");
    impl->characters.erase(id);
    impl->retired.insert(entry.body.GetIndexAndSequenceNumber());
    if(entry.enabled) impl->changed(entry);
    if(entry.enabled) api.RemoveBody(entry.body);
    api.DestroyBody(entry.body); impl->bodies.erase(id); impl->names.erase(entry.body.GetIndexAndSequenceNumber());
    impl->occupied[entry.body.GetIndex()]=false;
    std::erase_if(impl->ignored,[&](const Pair& pair){return pair.first==id||pair.second==id;});
}
bool PhysicsWorld::contains(const std::string& id) const { return impl->bodies.contains(id); }
std::size_t PhysicsWorld::size() const { return impl->bodies.size(); }
PhysicsPose PhysicsWorld::pose(const std::string& id) const {
    auto& api=impl->world.GetBodyInterface(); auto body=impl->get(id).body;
    auto q=api.GetRotation(body);
    const auto velocity=has_character(id)?impl->character(id).controller->GetLinearVelocity():api.GetLinearVelocity(body);
    return {Vector(api.GetPosition(body)),Vector(velocity),Vector(api.GetAngularVelocity(body)),
        glm::dquat(q.GetW(),q.GetX(),q.GetY(),q.GetZ()),api.IsActive(body)};
}
void PhysicsWorld::transform(const std::string& id,Vec3 p,glm::dquat q,bool wake) {
    auto position=Position(p); auto rotation=Rotation(q); auto& e=impl->get(id);
    if(has_character(id)) Upright(rotation);
    if(wake&&e.enabled) impl->changed(e);
    impl->world.GetBodyInterface().SetPositionAndRotation(e.body,position,rotation,impl->activation(e,wake));
    if(wake&&e.enabled) impl->changed(e);
    if(has_character(id)) {
        auto& c=impl->character(id); c.controller->SetPosition(position); c.controller->SetRotation(rotation);
        c.jump=0; impl->refresh_character(id);
    }
}
void PhysicsWorld::velocity(const std::string& id,Vec3 linear,Vec3 angular) {
    Range(linear,1e4,"velocity"); Range(angular,1e4,"angular velocity"); auto& e=impl->get(id);
    if(has_character(id)) {
        if(angular!=Vec3(0)) throw std::runtime_error("Character angular velocity is unsupported");
        auto& c=impl->character(id); c.controller->SetLinearVelocity(Vector(linear)); c.desired={linear.x,0,linear.z}; return;
    }
    if(e.settings.motion=="static") throw std::runtime_error("Static physics body has no velocity");
    // Set through the body lock to avoid accidentally activating a disabled body.
    { JPH::BodyLockWrite lock(impl->world.GetBodyLockInterface(),e.body);
      lock.GetBody().SetLinearVelocityClamped(Vector(linear)); lock.GetBody().SetAngularVelocityClamped(Vector(angular)); }
    if(impl->activation(e)==JPH::EActivation::Activate) impl->world.GetBodyInterface().ActivateBody(e.body);
}
void PhysicsWorld::force(const std::string& id,Vec3 force,Vec3 torque) {
    Range(force,1e12,"force"); Range(torque,1e12,"torque"); auto& e=impl->get(id); impl->dynamic(e);
    impl->world.GetBodyInterface().AddForceAndTorque(e.body,Vector(force),Vector(torque),JPH::EActivation::Activate);
}
void PhysicsWorld::impulse(const std::string& id,Vec3 impulse) {
    Range(impulse,1e12,"impulse"); auto& e=impl->get(id); impl->dynamic(e);
    impl->world.GetBodyInterface().AddImpulse(e.body,Vector(impulse));
}
void PhysicsWorld::motion(const std::string& id,const std::string& value) {
    auto next=Motion(value); auto& e=impl->get(id);
    if(has_character(id)&&value!="kinematic") throw std::runtime_error("Character body must stay kinematic");
    auto& api=impl->world.GetBodyInterface();
    api.SetMotionType(e.body,next,JPH::EActivation::DontActivate);
    e.settings.motion=value; api.SetObjectLayer(e.body,next==JPH::EMotionType::Static?0:1);
    impl->changed(e);
}
void PhysicsWorld::awake(const std::string& id,bool value) {
    auto& e=impl->get(id);
    if(has_character(id)&&!value) throw std::runtime_error("Disable a character instead of putting it to sleep");
    if(value&&(e.settings.motion=="static"||!e.enabled)) throw std::runtime_error("Cannot wake a static or disabled physics body");
    auto& api=impl->world.GetBodyInterface();
    if(value) api.ActivateBody(e.body); else api.DeactivateBody(e.body);
}
void PhysicsWorld::enabled(const std::string& id,bool value) {
    auto& e=impl->get(id); if(value==e.enabled) return;
    auto& api=impl->world.GetBodyInterface();
    e.enabled=value;
    if(value) api.AddBody(e.body,impl->activation(e));
    else {
        auto linear=api.GetLinearVelocity(e.body),angular=api.GetAngularVelocity(e.body);
        api.RemoveBody(e.body);
        if(e.settings.motion!="static") {
            JPH::BodyLockWrite lock(impl->world.GetBodyLockInterface(),e.body);
            lock.GetBody().SetLinearVelocityClamped(linear); lock.GetBody().SetAngularVelocityClamped(angular);
        }
    }
    impl->changed(e);
}
void PhysicsWorld::filter(const std::string& id,std::uint32_t layer,std::uint32_t mask) {
    if(layer>31) throw std::runtime_error("Physics layer must be 0..31");
    auto& e=impl->get(id); e.settings.layer=layer; e.settings.mask=mask;
    impl->world.GetBodyInterface().SetCollisionGroup(e.body,JPH::CollisionGroup(impl->masks,1u<<layer,mask)); impl->changed(e);
}
void PhysicsWorld::mass(const std::string& id,double mass) {
    Range(mass,.001,1e9,"mass"); auto& e=impl->get(id);
    { JPH::BodyLockWrite lock(impl->world.GetBodyLockInterface(),e.body);
      auto& b=lock.GetBody(); auto properties=b.GetShape()->GetMassProperties(); properties.ScaleToMass(float(mass));
      b.GetMotionPropertiesUnchecked()->SetMassProperties(JPH::EAllowedDOFs::All,properties); }
    e.settings.mass=mass; impl->changed(e);
    if(has_character(id)) impl->character(id).controller->SetMass(float(mass));
}
void PhysicsWorld::material(const std::string& id,double friction,double restitution) {
    Range(friction,0,10,"friction"); Range(restitution,0,1,"restitution"); auto& e=impl->get(id);
    auto& api=impl->world.GetBodyInterface(); api.SetFriction(e.body,float(friction)); api.SetRestitution(e.body,float(restitution));
    e.settings.friction=friction; e.settings.restitution=restitution; impl->changed(e);
}
void PhysicsWorld::gravity_scale(const std::string& id,double value) {
    Range(value,-1000,1000,"gravity scale"); auto& e=impl->get(id);
    { JPH::BodyLockWrite lock(impl->world.GetBodyLockInterface(),e.body);
      lock.GetBody().GetMotionPropertiesUnchecked()->SetGravityFactor(float(value)); }
    e.settings.gravity_scale=value; impl->changed(e);
}
void PhysicsWorld::damping(const std::string& id,double linear,double angular) {
    Range(linear,0,1000,"linear damping"); Range(angular,0,1000,"angular damping"); auto& e=impl->get(id);
    { JPH::BodyLockWrite lock(impl->world.GetBodyLockInterface(),e.body);
      auto* motion=lock.GetBody().GetMotionPropertiesUnchecked(); motion->SetLinearDamping(float(linear)); motion->SetAngularDamping(float(angular)); }
    e.settings.linear_damping=linear; e.settings.angular_damping=angular;
}
void PhysicsWorld::ignore_pair(const std::string& first,const std::string& second,bool value) {
    auto& a=impl->get(first); auto& b=impl->get(second);
    if(first==second) throw std::runtime_error("Cannot ignore a physics body against itself");
    auto pair=Ordered(first,second);
    if(value&&!impl->ignored.contains(pair)&&impl->ignored.size()>=MaxCollection) throw std::runtime_error("Physics ignored pairs exceed 65536");
    if(value) impl->ignored.insert(pair); else impl->ignored.erase(pair);
    impl->changed(a); impl->changed(b);
}
void PhysicsWorld::kinematic_target(const std::string& id,Vec3 p,glm::dquat q,double seconds) {
    auto position=Position(p); auto rotation=Rotation(q); Range(seconds,1e-6,1,"kinematic duration"); auto& e=impl->get(id);
    if(e.settings.motion!="kinematic"||!e.enabled) throw std::runtime_error("Physics target needs an enabled kinematic body");
    if(has_character(id)) throw std::runtime_error("Move a character through character_move");
    impl->world.GetBodyInterface().MoveKinematic(e.body,position,rotation,float(seconds));
}
void PhysicsWorld::validate_character(const PhysicsBody& body,const CharacterSettings& config) {
    validate(body); ValidateCharacterSettings(config);
    if(body.shape!="capsule"||body.motion!="kinematic"||body.sensor)
        throw std::runtime_error("Character needs a non-sensor kinematic capsule");
    Upright(Rotation(body.rotation));
    if(body.velocity!=Vec3(0)||body.angular_velocity!=Vec3(0))
        throw std::runtime_error("Character attachment needs a stationary body");
}
void PhysicsWorld::attach_character(const std::string& id,const CharacterSettings& config) {
    auto& body=impl->get(id);
    if(has_character(id)) throw std::runtime_error("Character controller already exists");
    auto& api=impl->world.GetBodyInterface(); const auto rotation=api.GetRotation(body.body);
    auto live=body.settings; live.rotation={rotation.GetW(),rotation.GetX(),rotation.GetY(),rotation.GetZ()};
    live.velocity=Vector(api.GetLinearVelocity(body.body)); live.angular_velocity=Vector(api.GetAngularVelocity(body.body));
    validate_character(live,config);
    JPH::CharacterVirtualSettings settings;
    settings.mID=JPH::CharacterID(body.body.GetIndexAndSequenceNumber());
    settings.mShape=QueryShape(body.settings); settings.mMass=float(body.settings.mass);
    settings.mMaxSlopeAngle=float(glm::radians(config.max_slope)); settings.mMaxStrength=float(config.max_strength);
    settings.mSupportingVolume=JPH::Plane(JPH::Vec3::sAxisY(),float(body.settings.half_height));
    Impl::Character c; c.settings=config;
    c.controller=new JPH::CharacterVirtual(&settings,api.GetPosition(body.body),rotation,0,&impl->world);
    // Character motion is solved virtually; its capsule still supplies gameplay contacts.
    { JPH::BodyLockWrite lock(impl->world.GetBodyLockInterface(),body.body);
      lock.GetBody().SetCollideKinematicVsNonDynamic(true); }
    impl->characters.emplace(id,std::move(c)); impl->refresh_character(id);
}
void PhysicsWorld::detach_character(const std::string& id) {
    if(!impl->characters.erase(id)) return;
    auto& body=impl->get(id);
    { JPH::BodyLockWrite lock(impl->world.GetBodyLockInterface(),body.body);
      lock.GetBody().SetCollideKinematicVsNonDynamic(body.settings.sensor); }
    impl->changed(body);
}
void PhysicsWorld::clone_character(const std::string& source,const std::string& target) {
    const auto& original=impl->character(source);
    attach_character(target,original.settings);
    auto& copy=impl->character(target); copy.desired=original.desired; copy.jump=original.jump;
    copy.controller->SetLinearVelocity(original.controller->GetLinearVelocity());
}
bool PhysicsWorld::has_character(const std::string& id) const { return impl->characters.contains(id); }
CharacterSettings PhysicsWorld::character_settings(const std::string& id) const { return impl->character(id).settings; }
void PhysicsWorld::configure_character(const std::string& id,const CharacterSettings& config) {
    ValidateCharacterSettings(config); auto& c=impl->character(id);
    c.settings=config; c.controller->SetMaxSlopeAngle(float(glm::radians(config.max_slope)));
    c.controller->SetMaxStrength(float(config.max_strength)); impl->refresh_character(id);
}
CharacterState PhysicsWorld::character_state(const std::string& id) const {
    const auto& c=impl->character(id); const auto& controller=*c.controller; const auto& body=impl->get(id);
    CharacterState result; result.position=Vector(controller.GetPosition()); result.velocity=Vector(controller.GetLinearVelocity());
    if(!body.enabled) { result.ground_state="disabled"; return result; }
    static constexpr const char* states[]={"on_ground","steep_ground","unsupported","in_air"};
    result.ground_state=states[int(controller.GetGroundState())]; result.grounded=impl->grounded(body,c);
    const auto ground=controller.GetGroundBodyID(); auto found=impl->names.find(ground.GetIndexAndSequenceNumber());
    if(found!=impl->names.end()&&impl->ground_available(body,c)) {
        result.ground_entity=found->second; result.ground_point=Vector(controller.GetGroundPosition());
        result.ground_normal=Vector(controller.GetGroundNormal()); result.ground_velocity=Vector(controller.GetGroundVelocity());
    } else result.ground_state="in_air";
    return result;
}
void PhysicsWorld::character_move(const std::string& id,Vec3 desired) {
    Range(desired,1e4,"character move velocity");
    if(desired.y!=0) throw std::runtime_error("Character move velocity must be horizontal (Y = 0)");
    impl->character(id).desired=desired;
}
bool PhysicsWorld::character_jump(const std::string& id,double speed) {
    Range(speed,.001,1e4,"character jump speed"); auto& c=impl->character(id);
    impl->refresh_character(id);
    if(!impl->grounded(impl->get(id),c)||c.jump>0||c.controller->GetLinearVelocity().GetY()-c.controller->GetGroundVelocity().GetY()>.1f) return false;
    c.jump=speed; return true;
}
bool PhysicsWorld::character_resize(const std::string& id,double radius,double half_height) {
    auto next=settings(id); const auto pose=this->pose(id);
    next.position=pose.position+Vec3(0,radius+half_height-next.radius-next.half_height,0);
    next.rotation=pose.rotation; next.radius=radius; next.half_height=half_height;
    return reshape_character(id,next);
}
bool PhysicsWorld::reshape_character(const std::string& id,const PhysicsBody& geometry) {
    auto& c=impl->character(id); auto& e=impl->get(id); auto next=e.settings;
    next.radius=geometry.radius; next.half_height=geometry.half_height; next.half_extents=geometry.half_extents;
    const auto shape=QueryShape(next); const auto position=Position(geometry.position); const auto rotation=Rotation(geometry.rotation);
    Upright(rotation);
    const auto before=c.controller->GetPosition(); const auto before_rotation=c.controller->GetRotation();
    c.controller->SetPosition(position); c.controller->SetRotation(rotation);
    if(!c.controller->SetShape(shape,.001f,{},{},Impl::CharacterFilter(*impl,e),{},impl->allocator)) {
        c.controller->SetPosition(before); c.controller->SetRotation(before_rotation); return false;
    }
    c.controller->SetSupportingVolume(JPH::Plane(JPH::Vec3::sAxisY(),float(next.half_height)));
    auto& api=impl->world.GetBodyInterface(); api.SetShape(e.body,shape,false,JPH::EActivation::DontActivate);
    api.SetPositionAndRotation(e.body,position,rotation,impl->activation(e)); e.settings=next;
    mass(id,next.mass); impl->refresh_character(id); return true;
}
void PhysicsWorld::gravity(Vec3 value) { impl->world.SetGravity(Vector(Range(value,1e5,"gravity"))); }
void PhysicsWorld::step(double seconds) {
    Range(seconds,1e-6,.1,"step duration");
    impl->advance_characters(seconds);
    auto before=impl->touching;
    for(auto pair:impl->dormant) impl->touching.erase(pair);
    impl->dormant.clear();
    const auto error=impl->world.Update(float(seconds),1,&impl->allocator,&impl->jobs);
    if(error!=JPH::EPhysicsUpdateError::None) throw std::runtime_error("Physics contact capacity exceeded");
    impl->retired.clear();
    // Jolt drops contacts when bodies sleep. Preserve gameplay overlap until the
    // actual shapes separate, without waking the resting bodies to obtain callbacks.
    for(const auto& [pair,previous]:before) if(!impl->touching.contains(pair)) {
        auto contact=previous;
        if(impl->sleeping_contact(pair,contact)) { impl->touching[pair]=contact; impl->dormant.insert(pair); }
    }
    impl->events.clear();
    for(const auto& [key,contact]:before) if(!impl->touching.contains(key)) {
        auto event=contact; event.phase="exit"; impl->events.push_back(std::move(event));
    }
    for(const auto& [key,contact]:impl->touching) {
        auto event=contact; event.phase=before.contains(key)?"stay":"enter"; impl->events.push_back(std::move(event));
    }
    std::sort(impl->events.begin(),impl->events.end(),[](const auto& a,const auto& b){
        const auto rank=[](const std::string& phase){return phase=="exit"?0:phase=="enter"?1:2;};
        return std::tuple(a.first,a.second,rank(a.phase))<std::tuple(b.first,b.second,rank(b.phase));
    });
}
const std::vector<PhysicsContact>& PhysicsWorld::contacts() const { return impl->events; }
namespace {
Json PartJson(const PhysicsPart& p) {
    Json vertices=Json::array(),triangles=Json::array();
    for(const auto& v:p.vertices) vertices.push_back(ToJson(v));
    for(const auto& t:p.triangles) triangles.push_back({t[0],t[1],t[2]});
    return {{"shape",p.shape},{"position",ToJson(p.position)},
        {"rotation",{p.rotation.w,p.rotation.x,p.rotation.y,p.rotation.z}},
        {"half_extents",ToJson(p.half_extents)},{"radius",p.radius},{"half_height",p.half_height},
        {"vertices",vertices},{"triangles",triangles}};
}
PhysicsPart ReadPart(const Json& j) {
    using namespace physics_checkpoint;
    Require(j.is_object()&&j.size()==8,"physics part fields"); PhysicsPart p;
    p.shape=FromJson<std::string>(j.at("shape")); p.position=FromJson<Vec3>(j.at("position"));
    const auto& q=j.at("rotation"); Require(q.is_array()&&q.size()==4,"physics part rotation");
    p.rotation={FromJson<double>(q.at(0)),FromJson<double>(q.at(1)),FromJson<double>(q.at(2)),FromJson<double>(q.at(3))};
    p.half_extents=FromJson<Vec3>(j.at("half_extents")); p.radius=FromJson<double>(j.at("radius")); p.half_height=FromJson<double>(j.at("half_height"));
    const auto& vertices=j.at("vertices"); Require(vertices.is_array(),"physics part vertices");
    for(const auto& v:vertices) p.vertices.push_back(FromJson<Vec3>(v));
    const auto& triangles=j.at("triangles"); Require(triangles.is_array(),"physics part triangles");
    for(const auto& t:triangles) { Require(t.is_array()&&t.size()==3,"physics part triangle"); p.triangles.push_back({UInt(t.at(0)),UInt(t.at(1)),UInt(t.at(2))}); }
    return p;
}
Json BodyJson(const PhysicsBody& p) {
    Json result={{"id",p.id},{"shape",p.shape},{"motion",p.motion},{"position",ToJson(p.position)},
        {"rotation",{p.rotation.w,p.rotation.x,p.rotation.y,p.rotation.z}},{"half_extents",ToJson(p.half_extents)},
        {"velocity",ToJson(p.velocity)},{"angular_velocity",ToJson(p.angular_velocity)},
        {"radius",p.radius},{"half_height",p.half_height},{"mass",p.mass},{"friction",p.friction},{"restitution",p.restitution},
        {"gravity_scale",p.gravity_scale},{"linear_damping",p.linear_damping},{"angular_damping",p.angular_damping},
        {"layer",p.layer},{"mask",p.mask},{"sensor",p.sensor},{"continuous",p.continuous}};
    if(!p.parts.empty()) { result["parts"]=Json::array(); for(const auto& part:p.parts) result["parts"].push_back(PartJson(part)); }
    return result;
}
PhysicsBody ReadBody(const Json& j) {
    using namespace physics_checkpoint;
    Require(j.is_object()&&(j.size()==20||j.size()==21),"body settings fields"); PhysicsBody p;
    p.id=FromJson<std::string>(j.at("id")); p.shape=FromJson<std::string>(j.at("shape")); p.motion=FromJson<std::string>(j.at("motion"));
    p.position=FromJson<Vec3>(j.at("position")); p.half_extents=FromJson<Vec3>(j.at("half_extents"));
    p.velocity=FromJson<Vec3>(j.at("velocity")); p.angular_velocity=FromJson<Vec3>(j.at("angular_velocity"));
    const auto& q=j.at("rotation"); Require(q.is_array()&&q.size()==4,"rotation fields");
    p.rotation={FromJson<double>(q.at(0)),FromJson<double>(q.at(1)),FromJson<double>(q.at(2)),FromJson<double>(q.at(3))};
    p.radius=FromJson<double>(j.at("radius")); p.half_height=FromJson<double>(j.at("half_height"));
    p.mass=FromJson<double>(j.at("mass")); p.friction=FromJson<double>(j.at("friction")); p.restitution=FromJson<double>(j.at("restitution"));
    p.gravity_scale=FromJson<double>(j.at("gravity_scale")); p.linear_damping=FromJson<double>(j.at("linear_damping")); p.angular_damping=FromJson<double>(j.at("angular_damping"));
    p.layer=UInt(j.at("layer"),31); p.mask=UInt(j.at("mask")); p.sensor=FromJson<bool>(j.at("sensor")); p.continuous=FromJson<bool>(j.at("continuous"));
    if(j.contains("parts")) { const auto& parts=j.at("parts"); Require(parts.is_array(),"physics parts"); for(const auto& part:parts) p.parts.push_back(ReadPart(part)); }
    PhysicsWorld::validate(p);
    return p;
}
Json ContactJson(const PhysicsContact& c) {
    return {{"first",c.first},{"second",c.second},{"phase",c.phase},{"point",ToJson(c.point)},
        {"normal",ToJson(c.normal)},{"sensor",c.sensor}};
}
PhysicsContact ReadContact(const Json& j,bool event) {
    using namespace physics_checkpoint;
    Require(j.is_object()&&j.size()==6,"contact fields");
    PhysicsContact c{FromJson<std::string>(j.at("first")),FromJson<std::string>(j.at("second")),FromJson<std::string>(j.at("phase")),
        FromJson<Vec3>(j.at("point")),FromJson<Vec3>(j.at("normal")),FromJson<bool>(j.at("sensor"))};
    Require(!c.first.empty()&&c.first<c.second&&c.first.size()<=1024&&c.second.size()<=1024,"contact entities");
    Require(event?(c.phase=="enter"||c.phase=="stay"||c.phase=="exit"):c.phase.empty(),"contact phase");
    Range(c.point,1e12,"contact point"); Require(std::abs(glm::dot(c.normal,c.normal)-1)<.002,"contact normal"); return c;
}
}
Json PhysicsWorld::checkpoint() const {
    using namespace physics_checkpoint;
    Recorder native; impl->world.SaveState(native);
    Json body_data=Json::array(),active=Json::array(),touching=Json::array(),ignored=Json::array();
    std::map<std::uint32_t,Recorder> states; std::map<std::uint32_t,BodyInfo> info;
    for(const auto& [id,e]:impl->bodies) {
        const auto native_id=e.body.GetIndexAndSequenceNumber(); auto& state=states[native_id];
        JPH::BodyLockRead lock(impl->world.GetBodyLockInterface(),e.body); const auto& body=lock.GetBody(); body.SaveState(state); ValidateBody(state);
        info.emplace(native_id,BodyInfo{e.enabled,body.IsActive(),!body.IsStatic(),&state});
        body_data.push_back({{"settings",BodyJson(e.settings)},{"native_id",native_id},{"enabled",e.enabled},
            {"cache_invalid",body.IsCollisionCacheInvalid()},{"state",state.hex()}});
    }
    ValidateWorld(native,info);
    JPH::BodyIDVector active_ids; impl->world.GetActiveBodies(JPH::EBodyType::RigidBody,active_ids);
    for(auto id:active_ids) active.push_back(id.GetIndexAndSequenceNumber());
    for(const auto& [pair,c]:impl->touching) touching.push_back({{"ids",{pair.first,pair.second}},
        {"contact",ContactJson(c)},{"dormant",impl->dormant.contains(pair)}});
    for(const auto& pair:impl->ignored) ignored.push_back({pair.first,pair.second});
    Json events=Json::array(); for(const auto& c:impl->events) events.push_back(ContactJson(c));
    Json result={{"version",1},{"backend","jolt-5.6.0-f64-le"},{"bodies",body_data},{"generations",impl->generations},
        {"retired",impl->retired},{"active",active},{"native",native.hex()},{"ignored",ignored},{"touching",touching},{"events",events}};
    if(!impl->characters.empty()) {
        result["version"]=2; result["characters"]=Json::object();
        for(const auto& [id,c]:impl->characters) {
            Recorder state; c.controller->SaveState(state); ValidateCharacter(state,impl->get(id).body.GetIndexAndSequenceNumber());
            result["characters"][id]={{"settings",{{"max_slope",c.settings.max_slope},{"step_height",c.settings.step_height},
                {"floor_snap",c.settings.floor_snap},{"max_strength",c.settings.max_strength}}},
                {"desired",ToJson(c.desired)},{"jump",c.jump},{"state",state.hex()}};
        }
    }
    Require(result.dump().size()<=48*1024*1024,"checkpoint exceeds 48 MiB"); return result;
}
void PhysicsWorld::restore(const Json& saved) {
    using namespace physics_checkpoint;
    Require(saved.is_object()&&saved.dump().size()<=48*1024*1024,"checkpoint fields or size");
    const auto version=UInt(saved.at("version"));
    Require((version==1||version==2)&&saved.size()==(version==1?10:11)&&saved.at("backend")=="jolt-5.6.0-f64-le","version or backend");
    const auto& generations=saved.at("generations"); Require(generations.is_array()&&generations.size()==MaxBodies,"generation table");
    const auto& bodies=saved.at("bodies"); Require(bodies.is_array()&&bodies.size()<=MaxBodies,"body list");
    PhysicsWorld next; std::map<std::uint32_t,Recorder> states; std::map<std::uint32_t,BodyInfo> info;
    auto& api=next.impl->world.GetBodyInterface();
    for(const auto& row:bodies) {
        Require(row.is_object()&&row.size()==5,"body fields");
        auto id=UInt(row.at("native_id")); NativeID(id); JPH::BodyID body_id(id);
        Require(!next.impl->occupied[body_id.GetIndex()]&&UInt(generations.at(body_id.GetIndex()),255)==body_id.GetSequenceNumber(),"body index or generation");
        auto settings=ReadBody(row.at("settings"));
        auto enabled=FromJson<bool>(row.at("enabled")); (void)FromJson<bool>(row.at("cache_invalid"));
        auto& state=states[id]; state.decode(row.at("state")); ValidateBody(state);
        next.add_with_id(settings,id,false); auto& entry=next.impl->get(settings.id);
        if(!enabled) { api.RemoveBody(body_id); entry.enabled=false; }
        info.emplace(id,BodyInfo{enabled,false,settings.motion!="static",&state});
    }
    for(std::size_t i=0;i<MaxBodies;++i) next.impl->generations[i]=std::uint8_t(UInt(generations.at(i),255));
    const auto& retired=saved.at("retired"); Require(retired.is_array()&&retired.size()<=MaxCollection,"retired body list");
    for(const auto& value:retired) { auto id=UInt(value); NativeID(id); Require(!info.contains(id)&&next.impl->retired.insert(id).second,"retired ID membership"); }
    const auto& active=saved.at("active"); Require(active.is_array()&&active.size()<=bodies.size(),"active body list");
    for(const auto& value:active) {
        auto id=UInt(value); auto it=info.find(id); Require(it!=info.end()&&it->second.enabled&&it->second.moving&&!it->second.active,"active ID membership");
        it->second.active=true;
    }
    Recorder native; native.decode(saved.at("native")); ValidateWorld(native,info);
    const auto& ignored=saved.at("ignored"); Require(ignored.is_array()&&ignored.size()<=MaxCollection,"ignored pair list");
    for(const auto& pair:ignored) {
        Require(pair.is_array()&&pair.size()==2,"ignored pair");
        auto a=FromJson<std::string>(pair.at(0)),b=FromJson<std::string>(pair.at(1));
        Require(a<b&&next.contains(a)&&next.contains(b)&&next.impl->ignored.emplace(a,b).second,"ignored pair membership");
    }
    const auto& contacts=saved.at("touching"); Require(contacts.is_array()&&contacts.size()<=16384,"contact list");
    for(const auto& row:contacts) {
        Require(row.is_object()&&row.size()==3,"contact row"); const auto& ids=row.at("ids"); Require(ids.is_array()&&ids.size()==2,"contact pair");
        auto a=UInt(ids.at(0)),b=UInt(ids.at(1)); NativeID(a); NativeID(b); Require(a<b,"contact order");
        auto contact=ReadContact(row.at("contact"),false);
        Require(next.impl->touching.emplace(BodyPair{a,b},contact).second,"duplicate contact");
        const auto na=next.impl->names.find(a),nb=next.impl->names.find(b);
        if(na!=next.impl->names.end()&&nb!=next.impl->names.end())
            Require(Ordered(na->second,nb->second)==Pair{contact.first,contact.second},"contact entity mismatch");
        if(FromJson<bool>(row.at("dormant"))) next.impl->dormant.emplace(a,b);
    }
    const auto& events=saved.at("events"); Require(events.is_array()&&events.size()<=32768,"event list");
    for(const auto& value:events) next.impl->events.push_back(ReadContact(value,true));
    // Restore activation order before sleep timers and force accumulators.
    for(const auto& value:active) api.ActivateBody(JPH::BodyID(UInt(value)));
    for(auto& [id,state]:states) {
        JPH::BodyLockWrite lock(next.impl->world.GetBodyLockInterface(),JPH::BodyID(id)); lock.GetBody().RestoreState(state);
        Require(!state.failed&&state.IsEOF(),"body restore failed");
    }
    Require(next.impl->world.RestoreState(native)&&!native.failed&&native.IsEOF(),"native restore failed");
    for(const auto& row:bodies) if(FromJson<bool>(row.at("cache_invalid"))) api.InvalidateContactCache(JPH::BodyID(UInt(row.at("native_id"))));
    if(version==2) {
        const auto& characters=saved.at("characters");
        Require(characters.is_object()&&!characters.empty()&&characters.size()<=bodies.size(),"character list");
        for(const auto& [id,row]:characters.items()) {
            Require(row.is_object()&&row.size()==4&&next.contains(id),"character fields or body");
            const auto& settings=row.at("settings"); Require(settings.is_object()&&settings.size()==4,"character settings fields");
            CharacterSettings config{FromJson<double>(settings.at("max_slope")),FromJson<double>(settings.at("step_height")),
                FromJson<double>(settings.at("floor_snap")),FromJson<double>(settings.at("max_strength"))};
            Recorder state; state.decode(row.at("state")); ValidateCharacter(state,next.impl->get(id).body.GetIndexAndSequenceNumber());
            next.attach_character(id,config); auto& c=next.impl->character(id);
            next.character_move(id,FromJson<Vec3>(row.at("desired"))); c.jump=Range(FromJson<double>(row.at("jump")),0,1e4,"queued jump speed");
            c.controller->RestoreState(state); Require(!state.failed&&state.IsEOF(),"character restore failed");
            const auto body=next.impl->get(id).body;
            Require(c.controller->GetPosition()==api.GetPosition(body)&&c.controller->GetRotation()==api.GetRotation(body),"character and body poses disagree");
        }
    }
    Require(next.checkpoint()==saved,"state cannot be restored exactly");
    impl.swap(next.impl);
}
PhysicsHit PhysicsWorld::raycast(Vec3 origin,Vec3 displacement,std::uint32_t mask,bool sensors,const std::string& exclude) const {
    auto start=Position(origin); Range(displacement,1e7,"ray displacement");
    if(glm::length(displacement)<1e-12) throw std::runtime_error("Physics ray must have nonzero length");
    QueryFilter filter(mask,sensors,impl->excluded(exclude));
    JPH::RRayCast ray(start,Vector(displacement)); JPH::RayCastResult hit;
    if(!impl->world.GetNarrowPhaseQuery().CastRay(ray,hit,{},{},filter)) return {};
    auto point=ray.GetPointOnRay(hit.mFraction);
    JPH::BodyLockRead lock(impl->world.GetBodyLockInterface(),hit.mBodyID);
    // A solid ray starting inside a shape has no surface point to define a normal.
    auto normal=hit.mFraction==0?-glm::normalize(displacement):Vector(lock.GetBody().GetWorldSpaceSurfaceNormal(hit.mSubShapeID2,point));
    return {true,impl->names.at(hit.mBodyID.GetIndexAndSequenceNumber()),Vector(point),normal,hit.mFraction};
}
PhysicsHit PhysicsWorld::cast_shape(const PhysicsBody& query,Vec3 displacement,std::uint32_t mask,bool sensors,const std::string& exclude) const {
    const auto shape=QueryShape(query); Range(displacement,1e7,"cast displacement");
    const auto origin=Position(query.position); const auto rotation=Rotation(query.rotation);
    const JPH::RShapeCast cast(shape,JPH::Vec3::sReplicate(1),JPH::RMat44::sRotationTranslation(rotation,origin),Vector(displacement));
    JPH::ShapeCastSettings settings;
    settings.mBackFaceModeConvex=JPH::EBackFaceMode::CollideWithBackFaces;
    settings.mReturnDeepestPoint=true;
    JPH::ClosestHitCollisionCollector<JPH::CastShapeCollector> hits;
    QueryFilter filter(mask,sensors,impl->excluded(exclude));
    impl->world.GetNarrowPhaseQuery().CastShape(cast,settings,origin,hits,{},{},filter);
    if(!hits.HadHit()) return {};
    const auto& hit=hits.mHit;
    auto normal=-Vector(hit.mPenetrationAxis); const auto length=glm::length(normal);
    normal=length>1e-12?normal/length:(glm::length(displacement)>1e-12?-glm::normalize(displacement):Vec3(0));
    return {true,impl->names.at(hit.mBodyID2.GetIndexAndSequenceNumber()),
        query.position+Vector(hit.mContactPointOn2),normal,std::clamp(double(hit.mFraction),0.,1.)};
}
std::vector<std::string> PhysicsWorld::overlap_sphere(Vec3 center,double radius,std::uint32_t mask,bool sensors,const std::string& exclude) const {
    PhysicsBody query; query.id="query"; query.shape="sphere"; query.position=center; query.radius=radius;
    return overlap_shape(query,mask,sensors,exclude);
}
std::vector<std::string> PhysicsWorld::overlap_shape(const PhysicsBody& query,std::uint32_t mask,bool sensors,const std::string& exclude) const {
    const auto shape=QueryShape(query); const auto position=Position(query.position);
    JPH::AllHitCollisionCollector<JPH::CollideShapeCollector> hits;
    QueryFilter filter(mask,sensors,impl->excluded(exclude));
    impl->world.GetNarrowPhaseQuery().CollideShape(shape,JPH::Vec3::sReplicate(1),
        JPH::RMat44::sRotationTranslation(Rotation(query.rotation),position),{},position,hits,{},{},filter);
    std::set<std::string> ids;
    for(const auto& hit:hits.mHits) ids.insert(impl->names.at(hit.mBodyID2.GetIndexAndSequenceNumber()));
    return {ids.begin(),ids.end()};
}
}
