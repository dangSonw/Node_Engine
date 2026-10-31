#pragma once
#include "values.hpp"
#include "collections.hpp"
#include "events.hpp"
#include "scene.hpp"
#include "input.hpp"
#include "camera.hpp"
#include "audio.hpp"
#include "ui.hpp"
#include "persistence.hpp"
#include "checkpoint.hpp"
#include "physics_world.hpp"
#include "physics_scene.hpp"
#include "animation_scene.hpp"
#include "random.hpp"
#include "game_time.hpp"
#include "flow.hpp"
#include "continuations.hpp"
#include "application.hpp"
#include "scene_session.hpp"
#include "scoped_variables.hpp"
#include "user_types.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <deque>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/quaternion.hpp>

namespace rt {
struct QuestRuntimeState {
    std::map<std::string,std::int64_t> objectives;
    bool active=false, complete=false;
};
struct Ctx {
    std::shared_ptr<SceneWorld> world;
    std::shared_ptr<EventSystem> events;
    std::shared_ptr<AudioSystem> audio;
    std::shared_ptr<UiSystem> ui;
    std::shared_ptr<GamePersistence> game_persistence;
    std::shared_ptr<SceneSession> scenes;
    std::string scene_name="main";
    std::shared_ptr<Continuations> continuations;
    std::shared_ptr<PhysicsWorld> physics;
    PhysicsScene physics_scene;
    AnimationScene animation;
    int64_t random_seed=0;
    uint64_t random_state=0;
    std::function<void(Ctx&)> fixed_update;
    bool physics_advancing=false;
    std::map<std::string, Value> variables;
    VariableStore global_variables, entity_variable_defaults;
    std::map<std::string, VariableStore> entity_variables;
    std::map<std::string, std::string> variable_scopes;
    // Entity -> item -> count. Inventory state is part of the scene snapshot.
    std::map<std::string, std::map<std::string, std::int64_t>> inventories;
    std::map<std::string, std::string> ai_states;
    Array<Vec2> streamed_chunks;
    std::map<std::string,double> health, shields;
    std::map<std::string,QuestRuntimeState> quests;
    std::map<std::string,double> profile_starts, profile_samples;
    std::string replication_authority="server";
    std::map<std::string,std::string> replicated_values;
    std::int64_t replication_revision=0;
    std::map<std::pair<std::string, std::string>, Value> locals;
    Json functions = Json::object();
    Json user_types = {{"structs",Json::array()},{"enums",Json::array()}};
    std::map<std::string,int> flow_nodes;
    std::map<std::pair<std::string,std::string>,FlowState> flow_states;
    std::vector<Value> parameters;
    int call_depth = 0, execution_depth = 0;
    std::set<std::string> keys;
    InputState input;
    SaveStorage saves;
    std::vector<std::string> logs;
    std::string self = "player", current_node;
    double dt = 1.0 / 60.0, time = 0;
    double time_scale=1, unscaled_dt=1.0/60.0, real_time=0, real_dt=1.0/60.0;
    double autosave_interval=0, autosave_elapsed=0;
    bool autosave_pending=false;
    bool time_frozen=false; // Captured at frame start, never changed by gameplay mid-frame.
    bool world_paused=false;
    // Host shutdown intent is never restored from saved gameplay state.
    bool quit_requested=false, quit_dispatched=false;
    unsigned long long frame = 0;
    int budget = 100000, remaining = 100000;
};
struct ExecutionScope {
    Ctx& ctx;
    explicit ExecutionScope(Ctx& c):ctx(c) { ++ctx.execution_depth; }
    ~ExecutionScope() { --ctx.execution_depth; }
};
struct CallDepthScope {
    Ctx& ctx;
    explicit CallDepthScope(Ctx& c):ctx(c) {
        if(ctx.call_depth>=128) throw std::runtime_error("Function call depth exceeds 128");
        ++ctx.call_depth;
    }
    ~CallDepthScope() { --ctx.call_depth; }
};
inline void Tick(Ctx& ctx, const std::string& node) {
    ctx.current_node = node;
    if (--ctx.remaining < 0) throw std::runtime_error("Instruction budget exceeded at node " + node);
}
inline int LoopCount(double n) {
    if (!std::isfinite(n) || n < 0 || n > 1000000) throw std::runtime_error("Loop count must be between 0 and 1000000");
    return static_cast<int>(n);
}
inline double Float(double v) { return finite(v); }
inline bool Boolean(bool v) { return v; }
inline std::string String(std::string v) { CheckValue(v); return v; }
inline EntityRef EntityReference(std::string id) { CheckValue(id); return {std::move(id)}; }
inline std::string EntityId(const EntityRef& value) { return value.id; }
inline bool ReferenceEqual(const EntityRef& a, const EntityRef& b) { return a==b; }
inline double Add(double a, double b) { return finite(a+b); }
inline double Subtract(double a, double b) { return finite(a-b); }
inline double Multiply(double a, double b) { return finite(a*b); }
inline double Divide(double a, double b) {
    if (b == 0) throw std::runtime_error("Division by zero");
    return finite(a/b);
}
inline double Min(double a, double b) { return std::min(a,b); }
inline double Max(double a, double b) { return std::max(a,b); }
inline double Clamp(double v, double lo, double hi) {
    if (lo > hi) throw std::runtime_error("Clamp minimum exceeds maximum");
    return std::clamp(v,lo,hi);
}
inline double Lerp(double a, double b, double t) { return finite(a+(b-a)*t); }
inline double Sin(double a) { return std::sin(a); }
inline double Cos(double a) { return std::cos(a); }
inline double Abs(double a) { return std::abs(a); }
inline bool Less(double a, double b) { return a<b; }
inline bool Greater(double a, double b) { return a>b; }
inline double Modulo(double a, double b) {
    if (b == 0) throw std::runtime_error("Modulo by zero");
    return finite(std::fmod(a, b));
}
inline double Power(double base, double exponent) {
    return finite(std::pow(base, exponent));
}
inline double Sqrt(double value) {
    if (value < 0) throw std::runtime_error("Square root of negative value");
    return finite(std::sqrt(value));
}
inline double Floor(double value) { return finite(std::floor(value)); }
inline double Ceil(double value) { return finite(std::ceil(value)); }
inline double Round(double value) { return finite(std::round(value)); }
inline double Tan(double radians) { return finite(std::tan(radians)); }
inline double Atan2(double y, double x) { return finite(std::atan2(y, x)); }
inline double InverseLerp(double a, double b, double value) {
    if (a == b) throw std::runtime_error("Inverse lerp range cannot be zero");
    return finite((value-a)/(b-a));
}
inline double SmoothStep(double a, double b, double value) {
    const double t = Clamp(InverseLerp(a, b, value), 0.0, 1.0);
    return finite(t*t*(3.0-2.0*t));
}
inline double RemapRange(double value, double input_min, double input_max, double output_min, double output_max) {
    if (input_min == input_max) throw std::runtime_error("Remap input range cannot be zero");
    return finite(output_min + (value-input_min)*(output_max-output_min)/(input_max-input_min));
}
inline bool Equal(double a, double b) { return a==b; }
inline bool NotEqual(double a, double b) { return a!=b; }
inline bool LessEqual(double a, double b) { return a<=b; }
inline bool GreaterEqual(double a, double b) { return a>=b; }
inline bool NearlyEqual(double a, double b, double epsilon) {
    if (epsilon < 0) throw std::runtime_error("Negative tolerance");
    return std::abs(a-b) <= epsilon;
}
inline bool And(bool a, bool b) { return a && b; }
inline bool Or(bool a, bool b) { return a || b; }
inline bool Not(bool a) { return !a; }
inline bool Xor(bool a, bool b) { return a != b; }
inline Vec3 MakeVector3(double x, double y, double z) { return finite(Vec3{x,y,z}); }
inline Vec3 VectorAdd(Vec3 a, Vec3 b) { return finite(a+b); }
inline Vec3 VectorSubtract(Vec3 a, Vec3 b) { return finite(a-b); }
inline Vec3 VectorLerp(Vec3 a, Vec3 b, double t) { return finite(a+(b-a)*t); }
inline double Distance(Vec3 a, Vec3 b) { return finite(glm::length(a-b)); }
inline Vec3 VectorScale(Vec3 v, double s) { return finite(v*s); }
inline double Magnitude(Vec3 v) { return finite(glm::length(v)); }
inline Vec3 Normalize(Vec3 v) { double n=Magnitude(v); return n > 0 ? v/n : Vec3{0}; }
inline double Dot(Vec3 a, Vec3 b) { return finite(glm::dot(a,b)); }
inline Vec3 Cross(Vec3 a, Vec3 b) { return finite(glm::cross(a,b)); }
inline double VectorX(Vec3 value) { return finite(value.x); }
inline double VectorY(Vec3 value) { return finite(value.y); }
inline double VectorZ(Vec3 value) { return finite(value.z); }
inline double AngleBetween(Vec3 a, Vec3 b) {
    const double na = Magnitude(a), nb = Magnitude(b);
    if (na <= 0 || nb <= 0) throw std::runtime_error("Angle between requires nonzero vectors");
    const double cosine = std::clamp(glm::dot(a,b)/(na*nb), -1.0, 1.0);
    return finite(std::acos(cosine));
}
inline Vec3 ProjectVector(Vec3 value, Vec3 on) {
    const double denominator = glm::dot(on,on);
    if (denominator <= 0) return Vec3{0};
    return finite(on * (glm::dot(value,on) / denominator));
}
inline Vec3 ReflectVector(Vec3 value, Vec3 normal) {
    const double magnitude = Magnitude(normal);
    if (magnitude <= 0) throw std::runtime_error("Reflect vector requires a nonzero normal");
    normal /= magnitude;
    return finite(value - 2.0 * glm::dot(value,normal) * normal);
}
inline Vec3 RotateVector(Vec3 value, Vec3 rotation) {
    value=finite(value); rotation=finite(rotation);
    glm::dmat4 matrix(1.0);
    matrix=glm::rotate(matrix,glm::radians(rotation.y),Vec3{0,1,0});
    matrix=glm::rotate(matrix,glm::radians(rotation.x),Vec3{1,0,0});
    matrix=glm::rotate(matrix,glm::radians(rotation.z),Vec3{0,0,1});
    return finite(Vec3{matrix * glm::dvec4(value,0.0)});
}
inline Quat QuaternionNormalize(Quat value) {
    value=finite(value); const double length=glm::length(value);
    if(length<=0) throw std::runtime_error("Quaternion normalize requires a nonzero quaternion");
    return finite(value/length);
}
inline Quat QuaternionFromEuler(Vec3 euler) {
    euler=finite(euler);
    glm::dmat4 matrix(1.0);
    matrix=glm::rotate(matrix,glm::radians(euler.y),Vec3{0,1,0});
    matrix=glm::rotate(matrix,glm::radians(euler.x),Vec3{1,0,0});
    matrix=glm::rotate(matrix,glm::radians(euler.z),Vec3{0,0,1});
    return finite(glm::quat_cast(glm::dmat3(matrix)));
}
inline Quat QuaternionFromAxisAngle(Vec3 axis, double degrees) {
    axis=finite(axis); degrees=finite(degrees); const double length=glm::length(axis);
    if(length<=0) throw std::runtime_error("Quaternion axis must be nonzero");
    return finite(glm::angleAxis(glm::radians(degrees),axis/length));
}
inline Quat QuaternionMultiply(Quat a, Quat b) { return finite(QuaternionNormalize(a)*QuaternionNormalize(b)); }
inline Quat QuaternionInverse(Quat value) { return finite(glm::inverse(QuaternionNormalize(value))); }
inline Quat QuaternionSlerp(Quat a, Quat b, double t) {
    t=finite(t); return finite(glm::slerp(QuaternionNormalize(a),QuaternionNormalize(b),t));
}
inline Vec3 QuaternionRotateVector(Vec3 value, Quat rotation) {
    value=finite(value); const auto q=QuaternionNormalize(rotation); const Vec3 qv{q.x,q.y,q.z};
    const Vec3 twice_cross=2.0*glm::cross(qv,value);
    return finite(value+q.w*twice_cross+glm::cross(qv,twice_cross));
}
inline Mat4 IdentityMatrix() { return Mat4(1.0); }
inline Mat4 MatrixMultiply(Mat4 a, Mat4 b) { return finite(a*b); }
inline Mat4 MatrixInverse(Mat4 value) {
    value=finite(value); const double determinant=glm::determinant(value);
    if(!std::isfinite(determinant) || std::abs(determinant)<=1e-12) throw std::runtime_error("Matrix inverse requires a nonsingular matrix");
    return finite(glm::inverse(value));
}
inline Vec3 TransformPoint(Mat4 matrix, Vec3 point) {
    matrix=finite(matrix); point=finite(point); const Vec4 result=matrix*Vec4(point,1.0);
    if(std::abs(result.w)<=1e-12) throw std::runtime_error("Transform point produced a zero homogeneous coordinate");
    return finite(Vec3(result)/result.w);
}
inline Vec3 TransformDirection(Mat4 matrix, Vec3 direction) {
    matrix=finite(matrix); direction=finite(direction); return finite(Vec3(matrix*Vec4(direction,0.0)));
}
inline Mat4 MakeTransformMatrix(Vec3 position, Quat rotation, Vec3 scale) {
    position=finite(position); scale=finite(scale); rotation=QuaternionNormalize(rotation);
    return finite(glm::translate(Mat4(1.0),position)*glm::mat4_cast(rotation)*glm::scale(Mat4(1.0),scale));
}
inline bool PointInBounds(Vec3 point, Vec3 minimum, Vec3 maximum) {
    point=finite(point); minimum=finite(minimum); maximum=finite(maximum);
    const Vec3 low{std::min(minimum.x,maximum.x),std::min(minimum.y,maximum.y),std::min(minimum.z,maximum.z)};
    const Vec3 high{std::max(minimum.x,maximum.x),std::max(minimum.y,maximum.y),std::max(minimum.z,maximum.z)};
    return point.x>=low.x && point.x<=high.x && point.y>=low.y && point.y<=high.y && point.z>=low.z && point.z<=high.z;
}
inline Vec3 ClosestPointOnSegment(Vec3 point, Vec3 a, Vec3 b) {
    point=finite(point); a=finite(a); b=finite(b); const Vec3 delta=b-a; const double length2=glm::dot(delta,delta);
    if(length2<=1e-24) return a;
    const double t=std::clamp(glm::dot(point-a,delta)/length2,0.0,1.0);
    return finite(a+t*delta);
}
inline Vec3 ClosestPointOnBounds(Vec3 point, Vec3 minimum, Vec3 maximum) {
    point=finite(point); minimum=finite(minimum); maximum=finite(maximum);
    const Vec3 low{std::min(minimum.x,maximum.x),std::min(minimum.y,maximum.y),std::min(minimum.z,maximum.z)};
    const Vec3 high{std::max(minimum.x,maximum.x),std::max(minimum.y,maximum.y),std::max(minimum.z,maximum.z)};
    return finite(Vec3{std::clamp(point.x,low.x,high.x),std::clamp(point.y,low.y,high.y),std::clamp(point.z,low.z,high.z)});
}
inline Vec3 RayPlaneIntersection(Vec3 origin, Vec3 direction, Vec3 plane_point, Vec3 plane_normal) {
    origin=finite(origin); direction=finite(direction); plane_point=finite(plane_point); plane_normal=finite(plane_normal);
    const double direction_length=glm::length(direction), normal_length=glm::length(plane_normal);
    if(direction_length<=1e-12) throw std::runtime_error("Ray direction must be nonzero");
    if(normal_length<=1e-12) throw std::runtime_error("Plane normal must be nonzero");
    const double denominator=glm::dot(direction,plane_normal);
    if(std::abs(denominator)<=1e-12) throw std::runtime_error("Ray is parallel to plane");
    const double t=glm::dot(plane_point-origin,plane_normal)/denominator;
    if(t<0) throw std::runtime_error("Plane intersection is behind ray origin");
    return finite(origin+t*direction);
}
inline double RaySphereIntersectionDistance(Vec3 origin, Vec3 direction, Vec3 center, double radius) {
    origin=finite(origin); direction=finite(direction); center=finite(center); radius=finite(radius);
    if(radius<=0) throw std::runtime_error("Sphere radius must be positive");
    const double a=glm::dot(direction,direction);
    if(a<=1e-24) throw std::runtime_error("Ray direction must be nonzero");
    const Vec3 offset=origin-center; const double half_b=glm::dot(offset,direction);
    const double c=glm::dot(offset,offset)-radius*radius; const double discriminant=half_b*half_b-a*c;
    if(discriminant<0) throw std::runtime_error("Ray does not intersect sphere");
    const double root=std::sqrt(discriminant); double t=(-half_b-root)/a;
    if(t<0) t=(-half_b+root)/a;
    if(t<0) throw std::runtime_error("Sphere intersection is behind ray origin");
    return finite(t*std::sqrt(a));
}
inline bool LineSegmentsIntersect2D(Vec3 a1, Vec3 a2, Vec3 b1, Vec3 b2) {
    a1=finite(a1); a2=finite(a2); b1=finite(b1); b2=finite(b2);
    const auto cross=[](Vec3 a,Vec3 b){return a.x*b.y-a.y*b.x;};
    const Vec3 r=a2-a1, s=b2-b1, q=b1-a1; const double denominator=cross(r,s);
    if(std::abs(denominator)<=1e-12) {
        if(std::abs(cross(q,r))>1e-12) return false;
        const auto between=[](double value,double low,double high){return value>=std::min(low,high)-1e-12 && value<=std::max(low,high)+1e-12;};
        return between(b1.x,a1.x,a2.x) || between(b1.y,a1.y,a2.y) || between(a1.x,b1.x,b2.x) || between(a1.y,b1.y,b2.y);
    }
    const double t=cross(q,s)/denominator, u=cross(q,r)/denominator;
    return t>=-1e-12 && t<=1.0+1e-12 && u>=-1e-12 && u<=1.0+1e-12;
}
inline Vec3 BoundsMin(const Array<Vec3>& points) {
    if(points.empty()) throw std::runtime_error("Bounds require at least one point");
    Vec3 result=finite(points.front());
    for(const auto& point:points) { const auto value=finite(point); result=Vec3{std::min(result.x,value.x),std::min(result.y,value.y),std::min(result.z,value.z)}; }
    return result;
}
inline Vec3 BoundsMax(const Array<Vec3>& points) {
    if(points.empty()) throw std::runtime_error("Bounds require at least one point");
    Vec3 result=finite(points.front());
    for(const auto& point:points) { const auto value=finite(point); result=Vec3{std::max(result.x,value.x),std::max(result.y,value.y),std::max(result.z,value.z)}; }
    return result;
}
inline double RayBoundsIntersectionDistance(Vec3 origin, Vec3 direction, Vec3 minimum, Vec3 maximum) {
    origin=finite(origin); direction=finite(direction); minimum=finite(minimum); maximum=finite(maximum);
    const double length=glm::length(direction);
    if(length<=1e-12) throw std::runtime_error("Ray direction must be nonzero");
    const Vec3 low{std::min(minimum.x,maximum.x),std::min(minimum.y,maximum.y),std::min(minimum.z,maximum.z)};
    const Vec3 high{std::max(minimum.x,maximum.x),std::max(minimum.y,maximum.y),std::max(minimum.z,maximum.z)};
    double near=0, far=std::numeric_limits<double>::infinity();
    for(int axis=0;axis<3;++axis) {
        const double o=origin[axis], d=direction[axis];
        if(std::abs(d)<=1e-12) {
            if(o<low[axis] || o>high[axis]) throw std::runtime_error("Ray does not intersect bounds");
            continue;
        }
        double a=(low[axis]-o)/d, b=(high[axis]-o)/d;
        if(a>b) std::swap(a,b);
        near=std::max(near,a); far=std::min(far,b);
        if(near>far) throw std::runtime_error("Ray does not intersect bounds");
    }
    return finite(near*length);
}
inline Vec3 ClosestPointOnTriangle(Vec3 point, Vec3 a, Vec3 b, Vec3 c) {
    point=finite(point); a=finite(a); b=finite(b); c=finite(c);
    const Vec3 ab=b-a, ac=c-a, ap=point-a;
    const double d1=glm::dot(ab,ap), d2=glm::dot(ac,ap);
    if(d1<=0 && d2<=0) return a;
    const Vec3 bp=point-b; const double d3=glm::dot(ab,bp), d4=glm::dot(ac,bp);
    if(d3>=0 && d4<=d3) return b;
    const double vc=d1*d4-d3*d2;
    if(vc<=0 && d1>=0 && d3<=0) return finite(a+(d1/(d1-d3))*ab);
    const Vec3 cp=point-c; const double d5=glm::dot(ab,cp), d6=glm::dot(ac,cp);
    if(d6>=0 && d5<=d6) return c;
    const double vb=d5*d2-d1*d6;
    if(vb<=0 && d2>=0 && d6<=0) return finite(a+(d2/(d2-d6))*ac);
    const double va=d3*d6-d5*d4;
    if(va<=0 && (d4-d3)>=0 && (d5-d6)>=0) return finite(b+((d4-d3)/((d4-d3)+(d5-d6)))*(c-b));
    const double denominator=va+vb+vc;
    if(std::abs(denominator)<=1e-24) {
        const Vec3 abp=ClosestPointOnSegment(point,a,b), acp=ClosestPointOnSegment(point,a,c), bcp=ClosestPointOnSegment(point,b,c);
        const double dab=glm::dot(abp-point,abp-point), dac=glm::dot(acp-point,acp-point), dbc=glm::dot(bcp-point,bcp-point);
        return dab<=dac && dab<=dbc ? abp : (dac<=dbc ? acp : bcp);
    }
    const double v=vb/denominator, w=vc/denominator;
    return finite(a+ab*v+ac*w);
}
inline bool SphereOverlapsBounds(Vec3 center, double radius, Vec3 minimum, Vec3 maximum) {
    center=finite(center); radius=finite(radius); minimum=finite(minimum); maximum=finite(maximum);
    if(radius<0) throw std::runtime_error("Sphere radius must be nonnegative");
    const Vec3 closest=ClosestPointOnBounds(center,minimum,maximum);
    const Vec3 delta=closest-center;
    return glm::dot(delta,delta)<=radius*radius;
}
inline double DistanceToPlane(Vec3 point, Vec3 plane_point, Vec3 plane_normal) {
    point=finite(point); plane_point=finite(plane_point); plane_normal=finite(plane_normal);
    const double length=glm::length(plane_normal);
    if(length<=1e-12) throw std::runtime_error("Plane normal must be nonzero");
    return finite(glm::dot(point-plane_point,plane_normal)/length);
}
inline Vec2 MakeVector2(double x, double y) { return finite(Vec2{x,y}); }
inline Vec2 Vector2Add(Vec2 a, Vec2 b) { return finite(a+b); }
inline Vec2 Vector2Subtract(Vec2 a, Vec2 b) { return finite(a-b); }
inline Vec2 Vector2Scale(Vec2 v, double s) { return finite(v*s); }
inline double Vector2Magnitude(Vec2 v) { return finite(glm::length(v)); }
inline Vec2 Vector2Normalize(Vec2 v) { double n=Vector2Magnitude(v); return n > 0 ? v/n : Vec2{0}; }
inline double Vector2Dot(Vec2 a, Vec2 b) { return finite(glm::dot(a,b)); }
inline double Vector2Distance(Vec2 a, Vec2 b) { return finite(glm::length(a-b)); }
inline Vec2 SolveTwoBoneIK(Vec2 root, Vec2 target, double upper_length, double lower_length) {
    root=finite(root); target=finite(target);
    if(!std::isfinite(upper_length)||!std::isfinite(lower_length)||upper_length<=0||lower_length<=0)
        throw std::runtime_error("Two bone IK requires positive finite lengths");
    const auto delta=target-root; const double raw=glm::length(delta);
    const double distance=std::clamp(raw,std::abs(upper_length-lower_length),upper_length+lower_length);
    const double angle=raw>1e-12?std::atan2(delta.y,delta.x):0.0;
    const double denominator=2.0*upper_length*std::max(distance,1e-12);
    const double cosine=std::clamp((upper_length*upper_length+distance*distance-lower_length*lower_length)/denominator,-1.0,1.0);
    const double elbow=std::acos(cosine);
    return finite(root+Vec2{upper_length*std::cos(angle+elbow),upper_length*std::sin(angle+elbow)});
}
inline Vec3 EvaluateCinematicCamera(Ctx& c, double time) {
    time=finite(time);
    const auto features=FeatureMetadata(c);
    if(!features.contains("3d") || !features.at("3d").is_object() ||
       !features.at("3d").contains("cinematic_camera") || !features.at("3d").at("cinematic_camera").is_array())
        throw std::runtime_error("Cinematic camera keyframes are not configured");
    const auto& keys=features.at("3d").at("cinematic_camera");
    if(keys.empty()) throw std::runtime_error("Cinematic camera requires at least one keyframe");
    auto key=[&](std::size_t index) {
        const auto& value=keys.at(index);
        if(!value.is_object() || !value.contains("time") || !value.contains("value") || !value.at("time").is_number() ||
           !value.at("value").is_array() || value.at("value").size()!=3)
            throw std::runtime_error("Invalid cinematic camera keyframe");
        const double t=value.at("time").get<double>();
        if(!std::isfinite(t)) throw std::runtime_error("Cinematic camera keyframe time must be finite");
        Vec3 position{value.at("value")[0].get<double>(),value.at("value")[1].get<double>(),value.at("value")[2].get<double>()};
        return std::pair(t,finite(position));
    };
    auto left=key(0);
    for(std::size_t index=1;index<keys.size();++index) {
        const auto right=key(index);
        if(right.first<=left.first) throw std::runtime_error("Cinematic camera keyframe times must increase");
        if(time<=right.first) {
            const double factor=std::clamp((time-left.first)/(right.first-left.first),0.0,1.0);
            return finite(left.second+(right.second-left.second)*factor);
        }
        left=right;
    }
    return left.second;
}
inline Array<Vec2> FindNavigationPath(Ctx& c, Vec2 start, Vec2 goal) {
    const auto features=FeatureMetadata(c);
    if(!features.contains("gameplay") || !features.at("gameplay").is_object() ||
       !features.at("gameplay").contains("navigation") || !features.at("gameplay").at("navigation").is_object())
        throw std::runtime_error("Navigation grid is not configured");
    const auto& navigation=features.at("gameplay").at("navigation");
    const auto grid=navigation.value("grid",Json::array());
    if(!grid.is_array() || grid.size()!=2 || !grid.at(0).is_number_integer() || !grid.at(1).is_number_integer())
        throw std::runtime_error("Navigation grid dimensions are invalid");
    const auto width=grid.at(0).get<std::int64_t>(), height=grid.at(1).get<std::int64_t>();
    if(width<1 || height<1 || width>4096 || height>4096) throw std::runtime_error("Navigation grid dimensions are out of range");
    auto cell=[&](Vec2 value) {
        value=finite(value);
        const auto x=std::llround(value.x), y=std::llround(value.y);
        if(std::abs(value.x-double(x))>1e-9 || std::abs(value.y-double(y))>1e-9 || x<0 || y<0 || x>=width || y>=height)
            throw std::runtime_error("Navigation path endpoint is outside the grid");
        return std::pair<std::int64_t,std::int64_t>{x,y};
    };
    const auto source=cell(start), destination=cell(goal);
    const auto key=[&](std::int64_t x,std::int64_t y){return y*width+x;};
    std::set<std::int64_t> blocked;
    const auto blocked_json=navigation.value("blocked",Json::array());
    if(!blocked_json.is_array()) throw std::runtime_error("Navigation blocked cells must be an array");
    for(const auto& item:blocked_json) {
        if(!item.is_array()||item.size()!=2||!item.at(0).is_number_integer()||!item.at(1).is_number_integer())
            throw std::runtime_error("Navigation blocked cell is invalid");
        const auto x=item.at(0).get<std::int64_t>(), y=item.at(1).get<std::int64_t>();
        if(x<0||y<0||x>=width||y>=height) throw std::runtime_error("Navigation blocked cell is outside the grid");
        blocked.insert(key(x,y));
    }
    Array<Vec2> result;
    const auto source_key=key(source.first,source.second), destination_key=key(destination.first,destination.second);
    if(blocked.contains(source_key)||blocked.contains(destination_key)) return result;
    std::deque<std::int64_t> queue; std::map<std::int64_t,std::int64_t> previous;
    queue.push_back(source_key); previous.emplace(source_key,-1);
    while(!queue.empty()) {
        const auto current=queue.front(); queue.pop_front(); if(current==destination_key) break;
        const auto x=current%width, y=current/width;
        for(const auto& neighbor:std::array<std::pair<std::int64_t,std::int64_t>,4>{{{x-1,y},{x+1,y},{x,y-1},{x,y+1}}}) {
            if(neighbor.first<0||neighbor.second<0||neighbor.first>=width||neighbor.second>=height) continue;
            const auto next=key(neighbor.first,neighbor.second);
            if(blocked.contains(next)||previous.contains(next)) continue;
            previous.emplace(next,current); queue.push_back(next);
        }
    }
    if(!previous.contains(destination_key)) return result;
    std::vector<std::int64_t> reverse; for(auto current=destination_key;current!=-1;current=previous.at(current)) reverse.push_back(current);
    CollectionSize(reverse.size()); result.reserve(reverse.size());
    for(auto it=reverse.rbegin();it!=reverse.rend();++it) result.push_back(Vec2{double(*it%width),double(*it/width)});
    return result;
}
inline std::int64_t InventoryCapacity(Ctx& c) {
    const auto features=FeatureMetadata(c);
    if(!features.contains("gameplay") || !features.at("gameplay").is_object() ||
       !features.at("gameplay").contains("inventory")) return 32;
    const auto& config=features.at("gameplay").at("inventory");
    if(!config.is_object()) throw std::runtime_error("Inventory configuration must be an object");
    const auto capacity=config.contains("capacity") ? config.at("capacity") : Json(32);
    if(!capacity.is_number_integer()) throw std::runtime_error("Inventory capacity must be an integer");
    const auto result=capacity.get<std::int64_t>();
    if(result<0 || result>65536) throw std::runtime_error("Inventory capacity must be between 0 and 65536");
    return result;
}
inline void ValidateInventoryItem(const EntityRef& entity, const std::string& item, std::int64_t count=1) {
    CheckValue(entity); CheckValue(item);
    if(entity.id.empty() || item.empty()) throw std::runtime_error("Inventory entity and item are required");
    if(count<=0) throw std::runtime_error("Inventory count must be positive");
}
inline bool InventoryAddItem(Ctx& c, EntityRef entity, std::string item, std::int64_t count) {
    ValidateInventoryItem(entity,item,count);
    if(!EntityExists(c,entity)) throw std::runtime_error("Inventory entity does not exist: "+entity.id);
    auto& items=c.inventories[entity.id];
    if(!items.contains(item) && static_cast<std::int64_t>(items.size())>=InventoryCapacity(c)) return false;
    const auto existing=items.contains(item) ? items.at(item) : 0;
    if(existing>std::numeric_limits<std::int64_t>::max()-count) throw std::runtime_error("Inventory count overflow");
    items[item]=existing+count;
    return true;
}
inline bool InventoryRemoveItem(Ctx& c, EntityRef entity, std::string item, std::int64_t count) {
    ValidateInventoryItem(entity,item,count);
    if(!EntityExists(c,entity)) throw std::runtime_error("Inventory entity does not exist: "+entity.id);
    auto owner=c.inventories.find(entity.id);
    if(owner==c.inventories.end()) return false;
    auto found=owner->second.find(item);
    if(found==owner->second.end() || found->second<count) return false;
    found->second-=count;
    if(found->second==0) owner->second.erase(found);
    if(owner->second.empty()) c.inventories.erase(owner);
    return true;
}
inline std::int64_t InventoryCount(Ctx& c, EntityRef entity, std::string item) {
    ValidateInventoryItem(entity,item);
    if(!EntityExists(c,entity)) throw std::runtime_error("Inventory entity does not exist: "+entity.id);
    auto owner=c.inventories.find(entity.id);
    if(owner==c.inventories.end()) return 0;
    auto found=owner->second.find(item);
    return found==owner->second.end() ? 0 : found->second;
}
inline bool InventoryHasItem(Ctx& c, EntityRef entity, std::string item) {
    return InventoryCount(c,std::move(entity),std::move(item))>0;
}
inline void ValidateAIState(const EntityRef& entity, const std::string& state) {
    CheckValue(entity); CheckValue(state);
    if(entity.id.empty() || state.empty()) throw std::runtime_error("AI entity and state are required");
    if(!std::set<std::string>{"idle","patrol","chase","flee","attack"}.contains(state))
        throw std::runtime_error("Unknown AI state: "+state);
}
inline void SetAIState(Ctx& c, EntityRef entity, std::string state) {
    ValidateAIState(entity,state);
    if(!EntityExists(c,entity)) throw std::runtime_error("AI entity does not exist: "+entity.id);
    c.ai_states[entity.id]=std::move(state);
}
inline std::string GetAIState(Ctx& c, EntityRef entity) {
    CheckValue(entity);
    if(entity.id.empty() || !EntityExists(c,entity)) throw std::runtime_error("AI entity does not exist: "+entity.id);
    auto found=c.ai_states.find(entity.id);
    return found==c.ai_states.end() ? "idle" : found->second;
}
inline bool IsAIState(Ctx& c, EntityRef entity, std::string state) {
    ValidateAIState(entity,state);
    return GetAIState(c,std::move(entity))==state;
}
inline Array<Vec2> UpdateWorldStreaming(Ctx& c, Vec2 center) {
    center=finite(center);
    const auto features=FeatureMetadata(c);
    if(!features.contains("gameplay") || !features.at("gameplay").is_object() ||
       !features.at("gameplay").contains("world_streaming")) {
        c.streamed_chunks.clear();
        return {};
    }
    const auto& config=features.at("gameplay").at("world_streaming");
    if(!config.is_object()) throw std::runtime_error("World streaming configuration must be an object");
    const auto radius_json=config.contains("radius") ? config.at("radius") : Json(1);
    if(!radius_json.is_number_integer()) throw std::runtime_error("World streaming radius must be an integer");
    const auto radius=radius_json.get<std::int64_t>();
    if(radius<0 || radius>64) throw std::runtime_error("World streaming radius must be between 0 and 64");
    const auto chunks=config.value("chunks",Json::array());
    if(!chunks.is_array() || chunks.size()>65536) throw std::runtime_error("World streaming chunks must be an array");
    const auto cx=std::llround(center.x), cy=std::llround(center.y);
    if(std::abs(center.x-double(cx))>1e-9 || std::abs(center.y-double(cy))>1e-9)
        throw std::runtime_error("World streaming center must be an integer cell");
    Array<Vec2> loaded;
    std::set<std::pair<std::int64_t,std::int64_t>> seen;
    for(const auto& chunk:chunks) {
        if(!chunk.is_array() || chunk.size()!=2 || !chunk.at(0).is_number_integer() || !chunk.at(1).is_number_integer())
            throw std::runtime_error("Invalid world streaming chunk");
        const auto x=chunk.at(0).get<std::int64_t>(), y=chunk.at(1).get<std::int64_t>();
        if(std::abs(x-cx)>radius || std::abs(y-cy)>radius || !seen.insert({x,y}).second) continue;
        loaded.push_back(Vec2{double(x),double(y)});
    }
    std::sort(loaded.begin(),loaded.end(),[](const Vec2& left,const Vec2& right){
        return left.x<right.x || (left.x==right.x && left.y<right.y);
    });
    c.streamed_chunks=loaded;
    return loaded;
}
inline void ValidateCombatEntity(Ctx& c, const EntityRef& entity) {
    CheckValue(entity);
    if(entity.id.empty() || !EntityExists(c,entity)) throw std::runtime_error("Combat entity does not exist: "+entity.id);
    c.health.try_emplace(entity.id,100.0); c.shields.try_emplace(entity.id,0.0);
}
inline std::tuple<double,bool> ApplyDamage(Ctx& c, EntityRef target, double amount) {
    ValidateCombatEntity(c,target); amount=finite(amount);
    if(amount<0) throw std::runtime_error("Damage cannot be negative");
    auto& shield=c.shields[target.id]; auto& health=c.health[target.id];
    const auto absorbed=std::min(shield,amount); shield-=absorbed; health-=amount-absorbed;
    return {amount-absorbed,health>0};
}
inline double GetHealth(Ctx& c, EntityRef target) { ValidateCombatEntity(c,target); return finite(c.health.at(target.id)); }
inline bool IsAlive(Ctx& c, EntityRef target) { return GetHealth(c,std::move(target))>0; }
inline void ValidateQuestText(const std::string& value,const char* field) {
    CheckValue(value); if(value.empty()) throw std::runtime_error(std::string("Quest ")+field+" is required");
}
inline bool StartQuest(Ctx& c, std::string quest) {
    ValidateQuestText(quest,"ID");
    auto found=c.quests.find(quest); if(found==c.quests.end()) return false;
    found->second.active=true; found->second.complete=false; return true;
}
inline bool AdvanceQuest(Ctx& c, std::string quest, std::string objective, std::int64_t amount) {
    ValidateQuestText(quest,"ID"); ValidateQuestText(objective,"objective");
    if(amount<=0) throw std::runtime_error("Quest progress amount must be positive");
    auto found=c.quests.find(quest); if(found==c.quests.end() || !found->second.active) return false;
    auto item=found->second.objectives.find(objective);
    if(item==found->second.objectives.end()) return false;
    item->second=std::max<std::int64_t>(0,item->second-amount);
    found->second.complete=!found->second.objectives.empty() && std::all_of(found->second.objectives.begin(),found->second.objectives.end(),[](const auto& entry){return entry.second==0;});
    return found->second.complete;
}
inline bool IsQuestActive(Ctx& c, std::string quest) {
    ValidateQuestText(quest,"ID"); auto found=c.quests.find(quest); return found!=c.quests.end() && found->second.active;
}
inline bool IsQuestComplete(Ctx& c, std::string quest) {
    ValidateQuestText(quest,"ID"); auto found=c.quests.find(quest); return found!=c.quests.end() && found->second.complete;
}
inline void ValidateProfileName(const std::string& name) {
    CheckValue(name); if(name.empty()) throw std::runtime_error("Profile sample name is required");
}
inline void BeginProfileSample(Ctx& c, std::string name) {
    ValidateProfileName(name);
    if(c.profile_starts.contains(name)) throw std::runtime_error("Profile sample is already active: "+name);
    c.profile_starts[name]=c.real_time;
}
inline double EndProfileSample(Ctx& c, std::string name) {
    ValidateProfileName(name);
    auto found=c.profile_starts.find(name);
    if(found==c.profile_starts.end()) throw std::runtime_error("Profile sample is not active: "+name);
    const auto elapsed=finite(std::max(0.0,c.real_time-found->second)); c.profile_starts.erase(found);
    c.profile_samples[name]+=elapsed; return elapsed;
}
inline double GetProfileSample(Ctx& c, std::string name) {
    ValidateProfileName(name); auto found=c.profile_samples.find(name); return found==c.profile_samples.end() ? 0.0 : finite(found->second);
}
inline void ValidateReplicationAuthority(const std::string& authority) {
    CheckValue(authority);
    if(!std::set<std::string>{"server","owner","client"}.contains(authority)) throw std::runtime_error("Invalid replication authority");
}
inline void ValidateReplicationKey(const std::string& key) {
    CheckValue(key); if(key.empty()) throw std::runtime_error("Replication key is required");
}
inline void SetReplicationAuthority(Ctx& c, std::string authority) {
    ValidateReplicationAuthority(authority); c.replication_authority=std::move(authority);
}
inline std::string GetReplicationAuthority(Ctx& c) { return c.replication_authority; }
inline bool PublishReplicatedValue(Ctx& c, std::string key, std::string value) {
    ValidateReplicationKey(key); CheckValue(value);
    if(c.replication_authority=="client") return false;
    c.replicated_values[std::move(key)]=std::move(value);
    if(c.replication_revision==std::numeric_limits<std::int64_t>::max()) throw std::runtime_error("Replication revision overflow");
    ++c.replication_revision; return true;
}
inline std::string GetReplicatedValue(Ctx& c, std::string key) {
    ValidateReplicationKey(key); auto found=c.replicated_values.find(key); return found==c.replicated_values.end() ? std::string{} : found->second;
}
inline std::int64_t GetReplicationRevision(Ctx& c) { return c.replication_revision; }
inline Vec4 MakeVector4(double x, double y, double z, double w) { return finite(Vec4{x,y,z,w}); }
inline Vec4 Vector4Add(Vec4 a, Vec4 b) { return finite(a+b); }
inline Vec4 Vector4Subtract(Vec4 a, Vec4 b) { return finite(a-b); }
inline Vec4 Vector4Scale(Vec4 v, double s) { return finite(v*s); }
inline double Vector4Magnitude(Vec4 v) { return finite(glm::length(v)); }
inline Vec4 Vector4Normalize(Vec4 v) { double n=Vector4Magnitude(v); return n > 0 ? v/n : Vec4{0}; }
inline double Vector4Dot(Vec4 a, Vec4 b) { return finite(glm::dot(a,b)); }
inline double Vector4Distance(Vec4 a, Vec4 b) { return finite(glm::length(a-b)); }
inline double DeltaTime(Ctx& c) { return c.dt; }
inline double GameTime(Ctx& c) { return c.time; }
inline double FrameCount(Ctx& c) { return static_cast<double>(c.frame); }
inline EntityRef Self(Ctx& c) { return {c.self}; }
inline void VariableName(const std::string& name) {
    if(name.empty() || name.find_first_not_of(" \t\r\n")==std::string::npos || name.size()>512 || name.find('\0')!=std::string::npos)
        throw std::runtime_error("Invalid variable name");
}
template<class T> T GetVariableAs(Ctx& c, const std::string& name) {
    const auto& value=GetVariableValue(c,name);
    if(!std::holds_alternative<T>(value)) throw std::runtime_error("Variable "+name+" is not "+TypeName<T>());
    return std::get<T>(value);
}
template<class T> void SetVariableAs(Ctx& c, const std::string& name, T value) {
    CheckValue(value); SetVariableValue(c,name,Value{std::move(value)});
}
template<class T> T GetScopedVariableAs(Ctx& c,const std::string& scope,const std::string& name,EntityRef owner={}) {
    const auto& value=GetScopedVariableValue(c,scope,name,std::move(owner));
    if(!std::holds_alternative<T>(value)) throw std::runtime_error("Variable "+name+" is not "+TypeName<T>());
    return std::get<T>(value);
}
template<class T> T GetGlobalVariableAs(Ctx& c,const std::string& name) { return GetScopedVariableAs<T>(c,"global",name); }
template<class T> void SetGlobalVariableAs(Ctx& c,const std::string& name,T value) { SetScopedVariableValue(c,"global",name,Value{std::move(value)}); }
template<class T> T GetSceneVariableAs(Ctx& c,const std::string& name) { return GetScopedVariableAs<T>(c,"scene",name); }
template<class T> void SetSceneVariableAs(Ctx& c,const std::string& name,T value) { SetScopedVariableValue(c,"scene",name,Value{std::move(value)}); }
template<class T> T GetEntityVariableAs(Ctx& c,EntityRef owner,const std::string& name) { return GetScopedVariableAs<T>(c,"entity",name,std::move(owner)); }
template<class T> void SetEntityVariableAs(Ctx& c,EntityRef owner,const std::string& name,T value) { SetScopedVariableValue(c,"entity",name,Value{std::move(value)},std::move(owner)); }
inline double GetVariable(Ctx& c, const std::string& name) { return GetVariableAs<double>(c,name); }
inline void SetVariable(Ctx& c, const std::string& name, double v) { SetVariableAs(c,name,v); }
inline bool KeyHeld(Ctx& c, std::string key) { return c.keys.contains(key); }
inline void Print(Ctx& c, std::string text) { c.logs.push_back(text); }
inline void Assert(Ctx&, bool condition, std::string text) { if(!condition) throw std::runtime_error(text); }
inline void LoadScene(Ctx& c, const Json& scene,const Json& identity_checkpoint=Json()) {
    c.user_types={{"structs",scene.value("struct_definitions",Json::array())},
                  {"enums",scene.value("enum_definitions",Json::array())}};
    c.saves=SaveStorage{c.saves.base, {}, {}, {}, true};
    c.ui=CreateUiSystem(scene.value("ui_assets",Json::array()));
    c.audio=CreateAudioSystem(scene.value("audio_assets",Json::array()));
    if(scene.contains("input") && scene.at("input").is_null()) throw std::runtime_error("Input bindings must be an object");
    LoadInput(c,scene.value("input",Json()));
    c.events.reset();
    c.physics.reset();
    c.physics_scene={}; c.fixed_update={}; c.physics_advancing=false;
    c.animation={};
    c.random_seed=0; c.random_state=0;
    c.flow_nodes.clear(); c.flow_states.clear();
    c.continuations.reset();
    c.world=CreateSceneWorld(scene,identity_checkpoint);
    if(identity_checkpoint.is_null()) LoadAuthoredPhysics(c);
    c.events=CreateEventSystem(c);
    c.variables.clear(); c.locals.clear(); c.parameters.clear(); c.call_depth=0;
    c.functions=Json::object(); c.logs.clear(); c.time=0; c.frame=0;
    c.quit_requested=c.quit_dispatched=false;
    c.world_paused=false;
    c.scenes.reset(); c.scene_name="main";
    c.autosave_interval=0; c.autosave_elapsed=0; c.autosave_pending=false;
    c.profile_starts.clear(); c.profile_samples.clear();
    c.replication_authority="server"; c.replicated_values.clear(); c.replication_revision=0;
    const auto autosave_features=FeatureMetadata(c);
    const auto autosave_gameplay=autosave_features.value("gameplay",Json::object());
    if(autosave_gameplay.is_object() && autosave_gameplay.contains("autosave")) {
        const auto& config=autosave_gameplay.at("autosave");
        if(!config.is_object() || !config.contains("interval") || !config.at("interval").is_number() || !std::isfinite(config.at("interval").get<double>()) || config.at("interval")<=0)
            throw std::runtime_error("Invalid autosave interval");
        c.autosave_interval=config.at("interval").get<double>();
    }
    if(scene.contains("autosave")) {
        const auto& state=scene.at("autosave");
        if(!state.is_object() || !state.contains("elapsed") || !state.at("elapsed").is_number() || !std::isfinite(state.at("elapsed").get<double>()) || state.at("elapsed")<0)
            throw std::runtime_error("Invalid saved autosave state");
        c.autosave_elapsed=state.at("elapsed").get<double>();
    }
    c.inventories.clear();
    if(scene.contains("inventories")) {
        const auto& saved=scene.at("inventories");
        if(!saved.is_object()) throw std::runtime_error("Inventories must be an object");
        const auto capacity=InventoryCapacity(c);
        for(const auto& [entity_id,items]:saved.items()) {
            CheckValue(entity_id);
            if(!EntityExists(c,{entity_id}) || !items.is_object()) throw std::runtime_error("Invalid saved inventory owner");
            if(items.size()>static_cast<std::size_t>(capacity)) throw std::runtime_error("Saved inventory exceeds capacity");
            auto& target=c.inventories[entity_id];
            for(const auto& [item,count]:items.items()) {
                CheckValue(item);
                if(item.empty() || !count.is_number_integer() || count.get<std::int64_t>()<=0)
                    throw std::runtime_error("Invalid saved inventory item");
                target[item]=count.get<std::int64_t>();
            }
        }
    }
    c.ai_states.clear();
    if(scene.contains("ai_states")) {
        const auto& saved=scene.at("ai_states");
        if(!saved.is_object()) throw std::runtime_error("AI states must be an object");
        for(const auto& [entity_id,state]:saved.items()) {
            if(!EntityExists(c,{entity_id}) || !state.is_string()) throw std::runtime_error("Invalid saved AI state");
            ValidateAIState({entity_id},state.get<std::string>());
            c.ai_states[entity_id]=state.get<std::string>();
        }
    }
    c.streamed_chunks.clear();
    if(scene.contains("streamed_chunks")) c.streamed_chunks=FromJson<Array<Vec2>>(scene.at("streamed_chunks"));
    c.health.clear(); c.shields.clear();
    const auto loaded_features=FeatureMetadata(c);
    const auto gameplay=loaded_features.value("gameplay",Json::object());
    if(gameplay.is_object() && gameplay.contains("replication") && gameplay.at("replication").is_object()) {
        const auto authority=gameplay.at("replication").value("authority",std::string("server"));
        ValidateReplicationAuthority(authority); c.replication_authority=authority;
    }
    if(scene.contains("replication")) {
        const auto& state=scene.at("replication");
        if(!state.is_object() || !state.contains("authority") || !state.at("authority").is_string() || !state.contains("revision") || !state.at("revision").is_number_integer() || !state.contains("values") || !state.at("values").is_object())
            throw std::runtime_error("Invalid saved replication state");
        ValidateReplicationAuthority(state.at("authority").get<std::string>()); c.replication_authority=state.at("authority").get<std::string>();
        if(state.at("revision").get<std::int64_t>()<0) throw std::runtime_error("Invalid replication revision");
        c.replication_revision=state.at("revision").get<std::int64_t>();
        for(const auto& [key,value]:state.at("values").items()) { ValidateReplicationKey(key); if(!value.is_string()) throw std::runtime_error("Invalid replicated value"); c.replicated_values[key]=value.get<std::string>(); }
    }
    if(gameplay.is_object() && gameplay.contains("combat") && gameplay.at("combat").is_object()) {
        const auto entities=gameplay.at("combat").value("entities",Json::object());
        if(!entities.is_object()) throw std::runtime_error("Combat entities must be an object");
        for(const auto& [entity_id,definition]:entities.items()) {
            if(!EntityExists(c,{entity_id}) || !definition.is_object()) throw std::runtime_error("Invalid combat entity definition");
            const auto health=definition.contains("health") ? definition.at("health") : Json(100.0);
            const auto shield=definition.contains("shield") ? definition.at("shield") : Json(0.0);
            if(!health.is_number() || !shield.is_number() || !std::isfinite(health.get<double>()) || !std::isfinite(shield.get<double>()) || health<0 || shield<0)
                throw std::runtime_error("Invalid combat health or shield");
            c.health[entity_id]=health.get<double>(); c.shields[entity_id]=shield.get<double>();
        }
    }
    if(scene.contains("health")) for(const auto& [entity_id,value]:scene.at("health").items()) {
        if(!EntityExists(c,{entity_id}) || !value.is_number() || !std::isfinite(value.get<double>()) || value<0) throw std::runtime_error("Invalid saved health");
        c.health[entity_id]=value.get<double>();
    }
    if(scene.contains("shields")) for(const auto& [entity_id,value]:scene.at("shields").items()) {
        if(!EntityExists(c,{entity_id}) || !value.is_number() || !std::isfinite(value.get<double>()) || value<0) throw std::runtime_error("Invalid saved shield");
        c.shields[entity_id]=value.get<double>();
    }
    c.quests.clear();
    if(gameplay.is_object() && gameplay.contains("quests")) {
        const auto definitions=gameplay.at("quests");
        if(!definitions.is_object()) throw std::runtime_error("Quest definitions must be an object");
        for(const auto& [quest_id,definition]:definitions.items()) {
            CheckValue(quest_id); if(quest_id.empty() || !definition.is_object()) throw std::runtime_error("Invalid quest definition");
            const auto objectives=definition.value("objectives",Json::object()); if(!objectives.is_object()) throw std::runtime_error("Quest objectives must be an object");
            QuestRuntimeState quest;
            for(const auto& [objective,amount]:objectives.items()) {
                CheckValue(objective); if(objective.empty() || !amount.is_number_integer() || amount.get<std::int64_t>()<0) throw std::runtime_error("Invalid quest objective");
                quest.objectives[objective]=amount.get<std::int64_t>();
            }
            c.quests[quest_id]=std::move(quest);
        }
    }
    if(scene.contains("quests")) {
        const auto& saved=scene.at("quests"); if(!saved.is_object()) throw std::runtime_error("Saved quests must be an object");
        for(const auto& [quest_id,value]:saved.items()) {
            if(!value.is_object() || !value.contains("active") || !value.at("active").is_boolean() || !value.contains("complete") || !value.at("complete").is_boolean() || !value.contains("objectives") || !value.at("objectives").is_object())
                throw std::runtime_error("Invalid saved quest");
            auto& quest=c.quests[quest_id]; quest.active=value.at("active").get<bool>(); quest.complete=value.at("complete").get<bool>();
            for(const auto& [objective,amount]:value.at("objectives").items()) {
                if(!amount.is_number_integer() || amount.get<std::int64_t>()<0) throw std::runtime_error("Invalid saved quest objective");
                quest.objectives[objective]=amount.get<std::int64_t>();
            }
        }
    }
    LoadVariableState(c,scene);
}
inline Json Snapshot(const Ctx& c) {
    Json ents=TransformSnapshot(c);
    Json variables=Json::object();
    for(const auto& [key,value]:c.variables) variables[key]=VariableJson(value);
    Json scene={{"version",1},{"entities",SceneEntities(c)},{"variables",variables},{"entity_serial",EntitySerial(c)}};
    if(!c.user_types.at("structs").empty()) scene["struct_definitions"]=c.user_types.at("structs");
    if(!c.user_types.at("enums").empty()) scene["enum_definitions"]=c.user_types.at("enums");
    SnapshotVariableState(c,scene);
    variables=scene.at("variables");
    if(EntityExists(c,{c.self}))
        for(const auto& [name,_]:c.entity_variable_defaults) variables[name]=VariableJson(GetVariableValue(c,name));
    const auto components=ComponentDefinitions(c);
    const auto materials=MaterialAssets(c);
    if(!materials.empty()) scene["material_assets"]=materials;
    const auto sprites=SpriteAssets(c);
    if(!sprites.empty()) scene["sprite_assets"]=sprites;
    const auto sprite_states=SpriteStateAssets(c);
    if(!sprite_states.empty()) scene["sprite_state_assets"]=sprite_states;
    const auto tilemaps=TilemapAssets(c);
    if(!tilemaps.empty()) scene["tilemap_assets"]=tilemaps;
    const auto features=FeatureMetadata(c);
    if(!features.empty()) scene["features"]=features;
    const auto sounds=AudioAssets(c);
    if(!sounds.empty()) scene["audio_assets"]=sounds;
    const auto widgets=UiAssets(c);
    if(!widgets.empty()) scene["ui_assets"]=widgets;
    if(!c.input.bindings.is_null()) scene["input"]=c.input.bindings;
    const auto camera=GetActiveCamera(c);
    if(!camera.id.empty()) scene["active_camera"]=camera.id;
    if(!components.empty()) scene["component_definitions"]=components;
    if(!c.inventories.empty()) {
        Json inventories=Json::object();
        for(const auto& [entity,items]:c.inventories) inventories[entity]=items;
        scene["inventories"]=std::move(inventories);
    }
    if(!c.ai_states.empty()) scene["ai_states"]=c.ai_states;
    if(!c.streamed_chunks.empty()) scene["streamed_chunks"]=ToJson(c.streamed_chunks);
    if(!c.health.empty()) scene["health"]=c.health;
    if(!c.shields.empty()) scene["shields"]=c.shields;
    if(!c.quests.empty()) {
        Json quests=Json::object();
        for(const auto& [id,quest]:c.quests) quests[id]={{"active",quest.active},{"complete",quest.complete},{"objectives",quest.objectives}};
        scene["quests"]=std::move(quests);
    }
    if(c.autosave_interval>0) scene["autosave"]={{"interval",c.autosave_interval},{"elapsed",c.autosave_elapsed}};
    Json result={{"entities",ents},{"variables",variables},{"scene",scene},
        {"logs",c.logs},{"frame",c.frame},{"time",c.time},{"timers",TimerSnapshot(c)},{"events",EventSnapshot(c)}};
    result["clock"]={{"scale",c.time_scale},{"real_time",c.real_time},{"unscaled_dt",c.unscaled_dt},{"dt",c.dt},{"paused",c.world_paused}};
    if(c.scenes) result["scene_session"]=SceneSessionSnapshot(c);
    SnapshotPrefabs(c,result["scene"],result);
    if(!c.saves.game.empty() || !c.saves.error.empty())
        result["persistence"]={{"game_id",c.saves.game},{"success",c.saves.ok},{"error",c.saves.error}};
    const auto audio=AudioSnapshot(c);
    if(!audio.is_null()) result["audio"]=audio;
    const auto ui=UiSnapshot(c);
    if(!ui.is_null()) result["ui"]=ui;
    const auto physics=PhysicsSnapshot(c);
    if(!physics.is_null()) result["physics"]=physics;
    const auto animation=AnimationSnapshot(c);
    if(!animation.empty()) result["animation"]=animation;
    if(!c.profile_samples.empty() || !c.profile_starts.empty())
        result["profiling"]={{"samples",c.profile_samples},{"active",c.profile_starts}};
    if(c.replication_revision>0 || !c.replicated_values.empty() || c.replication_authority!="server")
        result["replication"]={{"authority",c.replication_authority},{"revision",c.replication_revision},{"values",c.replicated_values}};
    if(c.random_seed!=0 || c.random_state!=0) result["random"]=RandomCheckpoint(c);
    if(!c.flow_nodes.empty()) result["flow"]=FlowCheckpoint(c);
    if(c.continuations) result["continuations"]=ContinuationCheckpoint(c);
    return result;
}
Value dispatch(Ctx& c, int type, const std::vector<Value>& args);
std::vector<Value> dispatch_results(Ctx&, int, const std::vector<Value>&);
Value Evaluate(Ctx& c, const Json& expr);
std::optional<std::vector<Value>> Execute(Ctx& c, const Json& statements);
std::vector<Value> Invoke(Ctx& c, int function, std::vector<Value> args);
}
