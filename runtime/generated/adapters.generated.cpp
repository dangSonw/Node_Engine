// Generated from nodes/registry.yaml. Do not edit.
#include "node_code.hpp"
#include <tuple>
namespace rt {
Value dispatch(Ctx& ctx, int type, const std::vector<Value>& args) {
    switch(type) {
    case 3001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Float(std::get<double>(args.at(0)));
    case 3002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Boolean(std::get<bool>(args.at(0)));
    case 3003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::String(std::get<std::string>(args.at(0)));
    case 3004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariable(ctx, std::get<std::string>(args.at(0)));
    case 3005:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariable(ctx, std::get<std::string>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 3050:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::FormatFloat(std::get<double>(args.at(0)));
    case 3051:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::FormatInteger(std::get<std::int64_t>(args.at(0)));
    case 3052:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ConcatStrings(std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3053:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::StringEqual(std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3054:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::FormatBoolean(std::get<bool>(args.at(0)));
    case 3055:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::StringSplit(std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3056:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::StringReplace(std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::string>(args.at(2)));
    case 3057:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::StringJoin(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3058:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::EntityId(std::get<rt::EntityRef>(args.at(0)));
    case 3059:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ReferenceEqual(std::get<rt::EntityRef>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 3090:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Integer(std::get<std::int64_t>(args.at(0)));
    case 3101:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<std::int64_t>(ctx, std::get<std::string>(args.at(0)));
    case 3102:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<bool>(ctx, std::get<std::string>(args.at(0)));
    case 3103:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<std::string>(ctx, std::get<std::string>(args.at(0)));
    case 3104:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Vec3>(ctx, std::get<std::string>(args.at(0)));
    case 3105:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::EntityRef>(ctx, std::get<std::string>(args.at(0)));
    case 3106:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Vec2>(ctx, std::get<std::string>(args.at(0)));
    case 3107:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Vec4>(ctx, std::get<std::string>(args.at(0)));
    case 3108:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Quat>(ctx, std::get<std::string>(args.at(0)));
    case 3109:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Mat4>(ctx, std::get<std::string>(args.at(0)));
    case 3111:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<std::int64_t>(ctx, std::get<std::string>(args.at(0)), std::get<std::int64_t>(args.at(1))); return 0.0;
    case 3112:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<bool>(ctx, std::get<std::string>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 3113:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<std::string>(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 3114:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Vec3>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 3115:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::EntityRef>(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1))); return 0.0;
    case 3116:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Vec2>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec2>(args.at(1))); return 0.0;
    case 3117:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Vec4>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec4>(args.at(1))); return 0.0;
    case 3118:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Quat>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Quat>(args.at(1))); return 0.0;
    case 3119:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Mat4>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Mat4>(args.at(1))); return 0.0;
    case 3200:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<double>>(ctx, std::get<std::string>(args.at(0)));
    case 3201:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 3202:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 3203:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 3204:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 3205:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 3206:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 3207:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 3208:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 3209:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 3210:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<double>>(args.at(1))); return 0.0;
    case 3211:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::int64_t>>(args.at(1))); return 0.0;
    case 3212:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<bool>>(args.at(1))); return 0.0;
    case 3213:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::string>>(args.at(1))); return 0.0;
    case 3214:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec3>>(args.at(1))); return 0.0;
    case 3215:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::EntityRef>>(args.at(1))); return 0.0;
    case 3216:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec2>>(args.at(1))); return 0.0;
    case 3217:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec4>>(args.at(1))); return 0.0;
    case 3218:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Quat>>(args.at(1))); return 0.0;
    case 3219:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Mat4>>(args.at(1))); return 0.0;
    case 3220:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<double>(std::get<rt::Array<double>>(args.at(0)));
    case 3221:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)));
    case 3222:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<bool>(std::get<rt::Array<bool>>(args.at(0)));
    case 3223:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<std::string>(std::get<rt::Array<std::string>>(args.at(0)));
    case 3224:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)));
    case 3225:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)));
    case 3226:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)));
    case 3227:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)));
    case 3228:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)));
    case 3229:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateArray<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)));
    case 3230:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<double>(std::get<rt::Array<double>>(args.at(0)), std::get<double>(args.at(1)));
    case 3231:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3232:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<bool>(args.at(1)));
    case 3233:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3234:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 3235:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 3236:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 3237:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 3238:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 3239:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayAppend<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<rt::Mat4>(args.at(1)));
    case 3240:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<double>(std::get<rt::Array<double>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<double>(args.at(2)));
    case 3241:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3242:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<bool>(args.at(2)));
    case 3243:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::string>(args.at(2)));
    case 3244:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 3245:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::EntityRef>(args.at(2)));
    case 3246:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Vec2>(args.at(2)));
    case 3247:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Vec4>(args.at(2)));
    case 3248:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Quat>(args.at(2)));
    case 3249:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArrayInsert<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Mat4>(args.at(2)));
    case 3250:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<double>(std::get<rt::Array<double>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3251:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3252:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3253:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3254:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3255:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3256:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3257:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3258:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3259:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayRemoveAt<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3260:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<double>(std::get<rt::Array<double>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3261:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3262:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3263:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3264:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3265:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3266:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3267:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3268:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3269:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayGet<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3270:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<double>(std::get<rt::Array<double>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<double>(args.at(2)));
    case 3271:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3272:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<bool>(args.at(2)));
    case 3273:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::string>(args.at(2)));
    case 3274:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 3275:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::EntityRef>(args.at(2)));
    case 3276:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Vec2>(args.at(2)));
    case 3277:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Vec4>(args.at(2)));
    case 3278:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Quat>(args.at(2)));
    case 3279:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySet<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<rt::Mat4>(args.at(2)));
    case 3280:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<double>(std::get<rt::Array<double>>(args.at(0)));
    case 3281:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)));
    case 3282:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<bool>(std::get<rt::Array<bool>>(args.at(0)));
    case 3283:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<std::string>(std::get<rt::Array<std::string>>(args.at(0)));
    case 3284:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)));
    case 3285:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)));
    case 3286:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)));
    case 3287:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)));
    case 3288:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)));
    case 3289:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayLength<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)));
    case 3290:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<double>(std::get<rt::Array<double>>(args.at(0)), std::get<double>(args.at(1)));
    case 3291:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3292:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<bool>(args.at(1)));
    case 3293:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3294:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 3295:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 3296:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 3297:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 3298:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 3299:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayContains<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<rt::Mat4>(args.at(1)));
    case 3300:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<double>(std::get<rt::Array<double>>(args.at(0)), std::get<double>(args.at(1)));
    case 3301:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3302:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<bool>(args.at(1)));
    case 3303:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3304:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 3305:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 3306:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 3307:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 3308:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 3309:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayFind<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<rt::Mat4>(args.at(1)));
    case 3310:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<double>(std::get<rt::Array<double>>(args.at(0)));
    case 3311:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)));
    case 3312:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<bool>(std::get<rt::Array<bool>>(args.at(0)));
    case 3313:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<std::string>(std::get<rt::Array<std::string>>(args.at(0)));
    case 3314:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)));
    case 3315:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)));
    case 3316:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)));
    case 3317:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)));
    case 3318:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)));
    case 3319:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayReverse<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)));
    case 3320:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<double>(std::get<rt::Array<double>>(args.at(0)));
    case 3321:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)));
    case 3322:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<bool>(std::get<rt::Array<bool>>(args.at(0)));
    case 3323:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<std::string>(std::get<rt::Array<std::string>>(args.at(0)));
    case 3324:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)));
    case 3325:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)));
    case 3326:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)));
    case 3327:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)));
    case 3328:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)));
    case 3329:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ArrayClear<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)));
    case 3400:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<double>>(ctx, std::get<std::string>(args.at(0)));
    case 3401:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 3402:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 3403:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 3404:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 3405:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 3406:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 3407:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 3408:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 3409:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 3410:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<double>>(args.at(1))); return 0.0;
    case 3411:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<std::int64_t>>(args.at(1))); return 0.0;
    case 3412:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<bool>>(args.at(1))); return 0.0;
    case 3413:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<std::string>>(args.at(1))); return 0.0;
    case 3414:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec3>>(args.at(1))); return 0.0;
    case 3415:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::EntityRef>>(args.at(1))); return 0.0;
    case 3416:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec2>>(args.at(1))); return 0.0;
    case 3417:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec4>>(args.at(1))); return 0.0;
    case 3418:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Quat>>(args.at(1))); return 0.0;
    case 3419:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Mat4>>(args.at(1))); return 0.0;
    case 3420:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<double>(std::get<rt::Map<double>>(args.at(0)));
    case 3421:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)));
    case 3422:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<bool>(std::get<rt::Map<bool>>(args.at(0)));
    case 3423:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<std::string>(std::get<rt::Map<std::string>>(args.at(0)));
    case 3424:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)));
    case 3425:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)));
    case 3426:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)));
    case 3427:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)));
    case 3428:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)));
    case 3429:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateMap<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)));
    case 3430:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<double>(std::get<rt::Map<double>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3431:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3432:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<bool>(std::get<rt::Map<bool>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3433:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<std::string>(std::get<rt::Map<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3434:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3435:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3436:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3437:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3438:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3439:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapGet<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3440:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<double>(std::get<rt::Map<double>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<double>(args.at(2)));
    case 3441:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3442:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<bool>(std::get<rt::Map<bool>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<bool>(args.at(2)));
    case 3443:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<std::string>(std::get<rt::Map<std::string>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::string>(args.at(2)));
    case 3444:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 3445:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::EntityRef>(args.at(2)));
    case 3446:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Vec2>(args.at(2)));
    case 3447:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Vec4>(args.at(2)));
    case 3448:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Quat>(args.at(2)));
    case 3449:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MapSet<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Mat4>(args.at(2)));
    case 3450:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<double>(std::get<rt::Map<double>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3451:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3452:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<bool>(std::get<rt::Map<bool>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3453:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<std::string>(std::get<rt::Map<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3454:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3455:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3456:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3457:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3458:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3459:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapRemove<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3460:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<double>(std::get<rt::Map<double>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3461:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3462:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<bool>(std::get<rt::Map<bool>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3463:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<std::string>(std::get<rt::Map<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3464:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3465:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3466:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3467:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3468:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3469:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MapHasKey<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3470:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<double>(std::get<rt::Map<double>>(args.at(0)));
    case 3471:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)));
    case 3472:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<bool>(std::get<rt::Map<bool>>(args.at(0)));
    case 3473:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<std::string>(std::get<rt::Map<std::string>>(args.at(0)));
    case 3474:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)));
    case 3475:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)));
    case 3476:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)));
    case 3477:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)));
    case 3478:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)));
    case 3479:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapKeys<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)));
    case 3480:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<double>(std::get<rt::Map<double>>(args.at(0)));
    case 3481:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)));
    case 3482:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<bool>(std::get<rt::Map<bool>>(args.at(0)));
    case 3483:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<std::string>(std::get<rt::Map<std::string>>(args.at(0)));
    case 3484:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)));
    case 3485:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)));
    case 3486:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)));
    case 3487:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)));
    case 3488:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)));
    case 3489:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapValues<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)));
    case 3490:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<double>(std::get<rt::Map<double>>(args.at(0)));
    case 3491:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)));
    case 3492:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<bool>(std::get<rt::Map<bool>>(args.at(0)));
    case 3493:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<std::string>(std::get<rt::Map<std::string>>(args.at(0)));
    case 3494:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)));
    case 3495:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)));
    case 3496:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)));
    case 3497:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)));
    case 3498:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)));
    case 3499:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapSize<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)));
    case 3500:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<double>(std::get<rt::Map<double>>(args.at(0)));
    case 3501:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<std::int64_t>(std::get<rt::Map<std::int64_t>>(args.at(0)));
    case 3502:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<bool>(std::get<rt::Map<bool>>(args.at(0)));
    case 3503:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<std::string>(std::get<rt::Map<std::string>>(args.at(0)));
    case 3504:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<rt::Vec3>(std::get<rt::Map<rt::Vec3>>(args.at(0)));
    case 3505:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<rt::EntityRef>(std::get<rt::Map<rt::EntityRef>>(args.at(0)));
    case 3506:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<rt::Vec2>(std::get<rt::Map<rt::Vec2>>(args.at(0)));
    case 3507:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<rt::Vec4>(std::get<rt::Map<rt::Vec4>>(args.at(0)));
    case 3508:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<rt::Quat>(std::get<rt::Map<rt::Quat>>(args.at(0)));
    case 3509:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MapClear<rt::Mat4>(std::get<rt::Map<rt::Mat4>>(args.at(0)));
    case 3600:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<double>>(ctx, std::get<std::string>(args.at(0)));
    case 3601:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 3602:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 3603:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 3604:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 3605:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 3606:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 3607:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 3608:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 3609:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 3610:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<double>>(args.at(1))); return 0.0;
    case 3611:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<std::int64_t>>(args.at(1))); return 0.0;
    case 3612:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<bool>>(args.at(1))); return 0.0;
    case 3613:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<std::string>>(args.at(1))); return 0.0;
    case 3614:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec3>>(args.at(1))); return 0.0;
    case 3615:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::EntityRef>>(args.at(1))); return 0.0;
    case 3616:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec2>>(args.at(1))); return 0.0;
    case 3617:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec4>>(args.at(1))); return 0.0;
    case 3618:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Quat>>(args.at(1))); return 0.0;
    case 3619:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Mat4>>(args.at(1))); return 0.0;
    case 3620:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<double>(std::get<rt::Set<double>>(args.at(0)));
    case 3621:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<std::int64_t>(std::get<rt::Set<std::int64_t>>(args.at(0)));
    case 3622:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<bool>(std::get<rt::Set<bool>>(args.at(0)));
    case 3623:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<std::string>(std::get<rt::Set<std::string>>(args.at(0)));
    case 3624:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<rt::Vec3>(std::get<rt::Set<rt::Vec3>>(args.at(0)));
    case 3625:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<rt::EntityRef>(std::get<rt::Set<rt::EntityRef>>(args.at(0)));
    case 3626:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<rt::Vec2>(std::get<rt::Set<rt::Vec2>>(args.at(0)));
    case 3627:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<rt::Vec4>(std::get<rt::Set<rt::Vec4>>(args.at(0)));
    case 3628:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<rt::Quat>(std::get<rt::Set<rt::Quat>>(args.at(0)));
    case 3629:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSet<rt::Mat4>(std::get<rt::Set<rt::Mat4>>(args.at(0)));
    case 3630:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<double>(std::get<rt::Set<double>>(args.at(0)), std::get<double>(args.at(1)));
    case 3631:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<std::int64_t>(std::get<rt::Set<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3632:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<bool>(std::get<rt::Set<bool>>(args.at(0)), std::get<bool>(args.at(1)));
    case 3633:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<std::string>(std::get<rt::Set<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3634:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<rt::Vec3>(std::get<rt::Set<rt::Vec3>>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 3635:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<rt::EntityRef>(std::get<rt::Set<rt::EntityRef>>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 3636:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<rt::Vec2>(std::get<rt::Set<rt::Vec2>>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 3637:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<rt::Vec4>(std::get<rt::Set<rt::Vec4>>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 3638:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<rt::Quat>(std::get<rt::Set<rt::Quat>>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 3639:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetAdd<rt::Mat4>(std::get<rt::Set<rt::Mat4>>(args.at(0)), std::get<rt::Mat4>(args.at(1)));
    case 3640:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<double>(std::get<rt::Set<double>>(args.at(0)), std::get<double>(args.at(1)));
    case 3641:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<std::int64_t>(std::get<rt::Set<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3642:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<bool>(std::get<rt::Set<bool>>(args.at(0)), std::get<bool>(args.at(1)));
    case 3643:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<std::string>(std::get<rt::Set<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3644:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<rt::Vec3>(std::get<rt::Set<rt::Vec3>>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 3645:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<rt::EntityRef>(std::get<rt::Set<rt::EntityRef>>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 3646:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<rt::Vec2>(std::get<rt::Set<rt::Vec2>>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 3647:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<rt::Vec4>(std::get<rt::Set<rt::Vec4>>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 3648:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<rt::Quat>(std::get<rt::Set<rt::Quat>>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 3649:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetRemove<rt::Mat4>(std::get<rt::Set<rt::Mat4>>(args.at(0)), std::get<rt::Mat4>(args.at(1)));
    case 3650:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<double>(std::get<rt::Set<double>>(args.at(0)), std::get<double>(args.at(1)));
    case 3651:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<std::int64_t>(std::get<rt::Set<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 3652:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<bool>(std::get<rt::Set<bool>>(args.at(0)), std::get<bool>(args.at(1)));
    case 3653:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<std::string>(std::get<rt::Set<std::string>>(args.at(0)), std::get<std::string>(args.at(1)));
    case 3654:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<rt::Vec3>(std::get<rt::Set<rt::Vec3>>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 3655:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<rt::EntityRef>(std::get<rt::Set<rt::EntityRef>>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 3656:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<rt::Vec2>(std::get<rt::Set<rt::Vec2>>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 3657:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<rt::Vec4>(std::get<rt::Set<rt::Vec4>>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 3658:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<rt::Quat>(std::get<rt::Set<rt::Quat>>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 3659:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SetContains<rt::Mat4>(std::get<rt::Set<rt::Mat4>>(args.at(0)), std::get<rt::Mat4>(args.at(1)));
    case 3660:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<double>(std::get<rt::Set<double>>(args.at(0)));
    case 3661:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<std::int64_t>(std::get<rt::Set<std::int64_t>>(args.at(0)));
    case 3662:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<bool>(std::get<rt::Set<bool>>(args.at(0)));
    case 3663:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<std::string>(std::get<rt::Set<std::string>>(args.at(0)));
    case 3664:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<rt::Vec3>(std::get<rt::Set<rt::Vec3>>(args.at(0)));
    case 3665:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<rt::EntityRef>(std::get<rt::Set<rt::EntityRef>>(args.at(0)));
    case 3666:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<rt::Vec2>(std::get<rt::Set<rt::Vec2>>(args.at(0)));
    case 3667:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<rt::Vec4>(std::get<rt::Set<rt::Vec4>>(args.at(0)));
    case 3668:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<rt::Quat>(std::get<rt::Set<rt::Quat>>(args.at(0)));
    case 3669:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetSize<rt::Mat4>(std::get<rt::Set<rt::Mat4>>(args.at(0)));
    case 3670:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<double>(std::get<rt::Set<double>>(args.at(0)));
    case 3671:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<std::int64_t>(std::get<rt::Set<std::int64_t>>(args.at(0)));
    case 3672:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<bool>(std::get<rt::Set<bool>>(args.at(0)));
    case 3673:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<std::string>(std::get<rt::Set<std::string>>(args.at(0)));
    case 3674:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<rt::Vec3>(std::get<rt::Set<rt::Vec3>>(args.at(0)));
    case 3675:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<rt::EntityRef>(std::get<rt::Set<rt::EntityRef>>(args.at(0)));
    case 3676:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<rt::Vec2>(std::get<rt::Set<rt::Vec2>>(args.at(0)));
    case 3677:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<rt::Vec4>(std::get<rt::Set<rt::Vec4>>(args.at(0)));
    case 3678:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<rt::Quat>(std::get<rt::Set<rt::Quat>>(args.at(0)));
    case 3679:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SetClear<rt::Mat4>(std::get<rt::Set<rt::Mat4>>(args.at(0)));
    case 3700:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<double>(std::get<rt::Array<double>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
    case 3701:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<rt::Array<std::int64_t>>(args.at(1)));
    case 3702:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<rt::Array<bool>>(args.at(1)));
    case 3703:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<rt::Array<std::string>>(args.at(1)));
    case 3704:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<rt::Array<rt::Vec3>>(args.at(1)));
    case 3705:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<rt::Array<rt::EntityRef>>(args.at(1)));
    case 3706:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<rt::Array<rt::Vec2>>(args.at(1)));
    case 3707:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<rt::Array<rt::Vec4>>(args.at(1)));
    case 3708:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<rt::Array<rt::Quat>>(args.at(1)));
    case 3709:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ArrayConcat<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<rt::Array<rt::Mat4>>(args.at(1)));
    case 3710:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<double>(std::get<rt::Array<double>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3711:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<std::int64_t>(std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3712:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<bool>(std::get<rt::Array<bool>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3713:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<std::string>(std::get<rt::Array<std::string>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3714:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<rt::Vec3>(std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3715:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<rt::EntityRef>(std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3716:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<rt::Vec2>(std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3717:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<rt::Vec4>(std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3718:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<rt::Quat>(std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 3719:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ArraySlice<rt::Mat4>(std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<std::int64_t>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 4001:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Add(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4002:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Subtract(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4003:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Multiply(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4004:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Divide(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4005:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Min(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4006:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Max(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4007:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::Clamp(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)));
    case 4008:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::Lerp(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)));
    case 4009:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Sin(std::get<double>(args.at(0)));
    case 4010:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Cos(std::get<double>(args.at(0)));
    case 4011:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Abs(std::get<double>(args.at(0)));
    case 4012:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Less(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4013:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Greater(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4014:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::NearlyEqual(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)));
    case 4015:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::And(std::get<bool>(args.at(0)), std::get<bool>(args.at(1)));
    case 4016:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Or(std::get<bool>(args.at(0)), std::get<bool>(args.at(1)));
    case 4017:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Not(std::get<bool>(args.at(0)));
    case 4020:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MakeVector3(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)));
    case 4021:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::VectorAdd(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4022:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::VectorScale(std::get<rt::Vec3>(args.at(0)), std::get<double>(args.at(1)));
    case 4023:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Normalize(std::get<rt::Vec3>(args.at(0)));
    case 4024:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Magnitude(std::get<rt::Vec3>(args.at(0)));
    case 4025:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Dot(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4026:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Cross(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4027:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::VectorSubtract(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4028:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::VectorLerp(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<double>(args.at(2)));
    case 4029:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Distance(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4030:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerAdd(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4031:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerSubtract(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4032:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerMultiply(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4033:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerLess(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4034:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerEqual(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4035:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IntegerToFloat(std::get<std::int64_t>(args.at(0)));
    case 4036:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::TruncateToInteger(std::get<double>(args.at(0)));
    case 4040:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Modulo(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4041:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Power(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4042:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Sqrt(std::get<double>(args.at(0)));
    case 4043:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Floor(std::get<double>(args.at(0)));
    case 4044:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Ceil(std::get<double>(args.at(0)));
    case 4045:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Round(std::get<double>(args.at(0)));
    case 4046:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Tan(std::get<double>(args.at(0)));
    case 4047:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Atan2(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4048:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::InverseLerp(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)));
    case 4049:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::SmoothStep(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)));
    case 4050:
        if(args.size()!=5) throw std::runtime_error("Invalid argument count");
        return rt::RemapRange(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3)), std::get<double>(args.at(4)));
    case 4051:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Equal(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4052:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::NotEqual(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4053:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::LessEqual(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4054:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GreaterEqual(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4055:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Xor(std::get<bool>(args.at(0)), std::get<bool>(args.at(1)));
    case 4056:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::BitwiseAnd(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4057:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::BitwiseOr(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4058:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::BitwiseXor(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4059:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerDivide(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4060:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerModulo(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4061:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IntegerAbs(std::get<std::int64_t>(args.at(0)));
    case 4062:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerMin(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4063:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerMax(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4064:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerLessEqual(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4065:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerGreaterEqual(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4066:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IntegerNotEqual(std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 4070:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::VectorX(std::get<rt::Vec3>(args.at(0)));
    case 4071:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::VectorY(std::get<rt::Vec3>(args.at(0)));
    case 4072:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::VectorZ(std::get<rt::Vec3>(args.at(0)));
    case 4073:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::AngleBetween(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4074:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ProjectVector(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4075:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::ReflectVector(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4076:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::RotateVector(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4080:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MakeVector2(std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 4081:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector2Add(std::get<rt::Vec2>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 4082:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector2Subtract(std::get<rt::Vec2>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 4083:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector2Scale(std::get<rt::Vec2>(args.at(0)), std::get<double>(args.at(1)));
    case 4084:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Vector2Magnitude(std::get<rt::Vec2>(args.at(0)));
    case 4085:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Vector2Normalize(std::get<rt::Vec2>(args.at(0)));
    case 4086:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector2Dot(std::get<rt::Vec2>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 4087:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector2Distance(std::get<rt::Vec2>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 4090:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::MakeVector4(std::get<double>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3)));
    case 4091:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector4Add(std::get<rt::Vec4>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 4092:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector4Subtract(std::get<rt::Vec4>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 4093:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector4Scale(std::get<rt::Vec4>(args.at(0)), std::get<double>(args.at(1)));
    case 4094:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Vector4Magnitude(std::get<rt::Vec4>(args.at(0)));
    case 4095:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::Vector4Normalize(std::get<rt::Vec4>(args.at(0)));
    case 4096:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector4Dot(std::get<rt::Vec4>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 4097:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::Vector4Distance(std::get<rt::Vec4>(args.at(0)), std::get<rt::Vec4>(args.at(1)));
    case 4100:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::QuaternionFromEuler(std::get<rt::Vec3>(args.at(0)));
    case 4101:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::QuaternionFromAxisAngle(std::get<rt::Vec3>(args.at(0)), std::get<double>(args.at(1)));
    case 4102:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::QuaternionMultiply(std::get<rt::Quat>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 4103:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::QuaternionNormalize(std::get<rt::Quat>(args.at(0)));
    case 4104:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::QuaternionInverse(std::get<rt::Quat>(args.at(0)));
    case 4105:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::QuaternionSlerp(std::get<rt::Quat>(args.at(0)), std::get<rt::Quat>(args.at(1)), std::get<double>(args.at(2)));
    case 4106:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::QuaternionRotateVector(std::get<rt::Vec3>(args.at(0)), std::get<rt::Quat>(args.at(1)));
    case 4110:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::IdentityMatrix();
    case 4111:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::MatrixMultiply(std::get<rt::Mat4>(args.at(0)), std::get<rt::Mat4>(args.at(1)));
    case 4112:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MatrixInverse(std::get<rt::Mat4>(args.at(0)));
    case 4113:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::TransformPoint(std::get<rt::Mat4>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4114:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::TransformDirection(std::get<rt::Mat4>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 4115:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::MakeTransformMatrix(std::get<rt::Vec3>(args.at(0)), std::get<rt::Quat>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 4120:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::PointInBounds(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 4121:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ClosestPointOnSegment(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 4122:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::ClosestPointOnBounds(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 4123:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::RayPlaneIntersection(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<rt::Vec3>(args.at(3)));
    case 4124:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::RaySphereIntersectionDistance(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<double>(args.at(3)));
    case 4125:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::LineSegmentsIntersect2D(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<rt::Vec3>(args.at(3)));
    case 4126:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::BoundsMin(std::get<rt::Array<rt::Vec3>>(args.at(0)));
    case 4127:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::BoundsMax(std::get<rt::Array<rt::Vec3>>(args.at(0)));
    case 4128:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::RayBoundsIntersectionDistance(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<rt::Vec3>(args.at(3)));
    case 4129:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::ClosestPointOnTriangle(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<rt::Vec3>(args.at(3)));
    case 4130:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::SphereOverlapsBounds(std::get<rt::Vec3>(args.at(0)), std::get<double>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<rt::Vec3>(args.at(3)));
    case 4131:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::DistanceToPlane(std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 5001:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::DeltaTime(ctx);
    case 5002:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GameTime(ctx);
    case 5003:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::FrameCount(ctx);
    case 5010:
        if(args.size()!=5) throw std::runtime_error("Invalid argument count");
        rt::StartTimer(ctx, std::get<std::string>(args.at(0)), std::get<double>(args.at(1)), std::get<bool>(args.at(2)), std::get<rt::EntityRef>(args.at(3)), std::get<bool>(args.at(4))); return 0.0;
    case 5011:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::StopTimer(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1))); return 0.0;
    case 5012:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::PauseTimer(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1))); return 0.0;
    case 5013:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::ResumeTimer(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1))); return 0.0;
    case 5014:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::TimerExists(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 5015:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IsTimerPaused(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 5016:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::TimerRemaining(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1)));
    case 5020:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SetRandomSeed(ctx, std::get<std::int64_t>(args.at(0))); return 0.0;
    case 5021:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetRandomSeed(ctx);
    case 5022:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::RandomFloat(ctx, std::get<double>(args.at(0)), std::get<double>(args.at(1)));
    case 5023:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::RandomInteger(ctx, std::get<std::int64_t>(args.at(0)), std::get<std::int64_t>(args.at(1)));
    case 5024:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::RandomBoolean(ctx, std::get<double>(args.at(0)));
    case 5025:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::RandomVector(ctx, std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 5026:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::RandomDirection(ctx);
    case 5030:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SetTimeScale(ctx, std::get<double>(args.at(0))); return 0.0;
    case 5031:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetTimeScale(ctx);
    case 5032:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::UnscaledDeltaTime(ctx);
    case 5033:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::RealTime(ctx);
    case 5034:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::FixedDeltaTime();
    case 5120:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<double>(ctx, std::get<rt::Array<double>>(args.at(0)));
    case 5121:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<std::int64_t>(ctx, std::get<rt::Array<std::int64_t>>(args.at(0)));
    case 5122:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<bool>(ctx, std::get<rt::Array<bool>>(args.at(0)));
    case 5123:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<std::string>(ctx, std::get<rt::Array<std::string>>(args.at(0)));
    case 5124:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<rt::Vec3>(ctx, std::get<rt::Array<rt::Vec3>>(args.at(0)));
    case 5125:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<rt::EntityRef>(ctx, std::get<rt::Array<rt::EntityRef>>(args.at(0)));
    case 5126:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<rt::Vec2>(ctx, std::get<rt::Array<rt::Vec2>>(args.at(0)));
    case 5127:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<rt::Vec4>(ctx, std::get<rt::Array<rt::Vec4>>(args.at(0)));
    case 5128:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<rt::Quat>(ctx, std::get<rt::Array<rt::Quat>>(args.at(0)));
    case 5129:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ShuffleArray<rt::Mat4>(ctx, std::get<rt::Array<rt::Mat4>>(args.at(0)));
    case 7001:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        rt::PauseWorld(ctx); return 0.0;
    case 7002:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        rt::ResumeWorld(ctx); return 0.0;
    case 7003:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::IsWorldPaused(ctx);
    case 7004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ChangeScene(ctx, std::get<std::string>(args.at(0)));
    case 7005:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::ReloadScene(ctx);
    case 7006:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetActiveScene(ctx);
    case 7007:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneNames(ctx);
    case 7008:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::SceneLoadSucceeded(ctx);
    case 7009:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneError(ctx);
    case 8001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::EntityReference(std::get<std::string>(args.at(0)));
    case 8002:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::Self(ctx);
    case 8003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::EntityExists(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8010:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::SpawnEntity(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 8011:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::CloneEntity(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 8012:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::DestroyEntity(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 8013:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityById(ctx, std::get<std::string>(args.at(0)));
    case 8014:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetAllEntities(ctx);
    case 8015:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::EntityCount(ctx);
    case 8016:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityName(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8017:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetEntityName(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 8018:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::FindEntitiesByName(ctx, std::get<std::string>(args.at(0)));
    case 8019:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetParent(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8020:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetParent(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::EntityRef>(args.at(1))); return 0.0;
    case 8021:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetChildren(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8022:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsEntityVisible(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8023:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVisibility(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 8024:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::AddEntityTag(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 8025:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::RemoveEntityTag(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 8026:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::HasEntityTag(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 8027:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::FindEntitiesByTag(ctx, std::get<std::string>(args.at(0)));
    case 8028:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetEntityActive(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 8029:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsEntityActive(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8030:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityActiveSelf(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8031:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityLayer(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8032:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetEntityLayer(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::int64_t>(args.at(1))); return 0.0;
    case 8033:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::FindEntitiesByLayer(ctx, std::get<std::int64_t>(args.at(0)), std::get<bool>(args.at(1)));
    case 8034:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::InstantiatePrefab(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1)), std::get<rt::Vec3>(args.at(2)));
    case 8035:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsPrefabInstance(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8036:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetPrefabAsset(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8037:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetPrefabRoot(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 8038:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetPrefabEntity(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 8039:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::ResetPrefabInstance(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 8040:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::ApplyPrefabOverrides(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 9001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetPosition(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 9002:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetPosition(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 9003:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::Translate(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 9004:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::Rotate(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 9005:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetScale(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 9006:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetRotation(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 9007:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetRotation(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 9008:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetScale(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 9010:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetWorldPosition(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 10001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::KeyHeld(ctx, std::get<std::string>(args.at(0)));
    case 10002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::KeyPressed(ctx, std::get<std::string>(args.at(0)));
    case 10003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::KeyReleased(ctx, std::get<std::string>(args.at(0)));
    case 10004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ActionHeld(ctx, std::get<std::string>(args.at(0)));
    case 10005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ActionPressed(ctx, std::get<std::string>(args.at(0)));
    case 10006:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ActionReleased(ctx, std::get<std::string>(args.at(0)));
    case 10007:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::InputAxis(ctx, std::get<std::string>(args.at(0)));
    case 10013:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::MousePosition(ctx);
    case 10014:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::MouseDelta(ctx);
    case 10015:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::MouseWheel(ctx);
    case 10016:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SetCursorVisible(ctx, std::get<bool>(args.at(0))); return 0.0;
    case 10017:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::LockCursor(ctx, std::get<bool>(args.at(0))); return 0.0;
    case 10018:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::ConnectedControllers(ctx);
    case 10019:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::GamepadAxis(ctx, std::get<std::int64_t>(args.at(0)), std::get<std::string>(args.at(1)), std::get<double>(args.at(2)));
    case 10021:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetInputContextEnabled(ctx, std::get<std::string>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 10022:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::InputContextEnabled(ctx, std::get<std::string>(args.at(0)));
    case 11001:
        if(args.size()!=6) throw std::runtime_error("Invalid argument count");
        rt::CreateBoxBody(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<std::string>(args.at(2)), std::get<double>(args.at(3)), std::get<bool>(args.at(4)), std::get<bool>(args.at(5))); return 0.0;
    case 11002:
        if(args.size()!=6) throw std::runtime_error("Invalid argument count");
        rt::CreateSphereBody(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<std::string>(args.at(2)), std::get<double>(args.at(3)), std::get<bool>(args.at(4)), std::get<bool>(args.at(5))); return 0.0;
    case 11003:
        if(args.size()!=7) throw std::runtime_error("Invalid argument count");
        rt::CreateCapsuleBody(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<std::string>(args.at(3)), std::get<double>(args.at(4)), std::get<bool>(args.at(5)), std::get<bool>(args.at(6))); return 0.0;
    case 11004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::RemoveBody(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 11005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::HasBody(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 11006:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetBodyType(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 11007:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetBodyType(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 11008:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetBodyMass(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 11009:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetBodyMass(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 11010:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetBodyVelocity(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 11011:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetBodyVelocity(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 11012:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetBodyAngularVelocity(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 11013:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetBodyAngularVelocity(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 11014:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::ApplyForce(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 11015:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::ApplyImpulse(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 11016:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::ApplyTorque(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 11017:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetBodyGravityScale(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 11018:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetBodyDamping(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2))); return 0.0;
    case 11019:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::WakeBody(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 11020:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SleepBody(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 11021:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsBodyAwake(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 11022:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetBodyEnabled(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 11023:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsBodyEnabled(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 11024:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetPhysicsMaterial(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2))); return 0.0;
    case 11025:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetCollisionMask(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::int64_t>(args.at(1))); return 0.0;
    case 11026:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::IgnoreCollisionPair(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::EntityRef>(args.at(1)), std::get<bool>(args.at(2))); return 0.0;
    case 11027:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SetPhysicsGravity(ctx, std::get<rt::Vec3>(args.at(0))); return 0.0;
    case 11028:
        if(args.size()!=5) throw std::runtime_error("Invalid argument count");
        return rt::PhysicsRaycast(ctx, std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<std::int64_t>(args.at(2)), std::get<bool>(args.at(3)), std::get<rt::EntityRef>(args.at(4)));
    case 11029:
        if(args.size()!=5) throw std::runtime_error("Invalid argument count");
        return rt::PhysicsOverlapSphere(ctx, std::get<rt::Vec3>(args.at(0)), std::get<double>(args.at(1)), std::get<std::int64_t>(args.at(2)), std::get<bool>(args.at(3)), std::get<rt::EntityRef>(args.at(4)));
    case 11030:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::MoveKinematicBody(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 11035:
        if(args.size()!=6) throw std::runtime_error("Invalid argument count");
        return rt::PhysicsOverlapBox(ctx, std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<std::int64_t>(args.at(3)), std::get<bool>(args.at(4)), std::get<rt::EntityRef>(args.at(5)));
    case 11036:
        if(args.size()!=7) throw std::runtime_error("Invalid argument count");
        return rt::PhysicsOverlapCapsule(ctx, std::get<rt::Vec3>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<rt::Vec3>(args.at(3)), std::get<std::int64_t>(args.at(4)), std::get<bool>(args.at(5)), std::get<rt::EntityRef>(args.at(6)));
    case 12001:
        if(args.size()!=8) throw std::runtime_error("Invalid argument count");
        rt::CreateCharacter(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3)), std::get<double>(args.at(4)), std::get<double>(args.at(5)), std::get<double>(args.at(6)), std::get<double>(args.at(7))); return 0.0;
    case 12002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::RemoveCharacter(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 12003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::HasCharacter(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 12004:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::CharacterMove(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 12005:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::CharacterJump(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)));
    case 12006:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::CharacterResize(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)));
    case 12007:
        if(args.size()!=5) throw std::runtime_error("Invalid argument count");
        rt::ConfigureCharacter(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3)), std::get<double>(args.at(4))); return 0.0;
    case 13001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetAnimationClips(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 13002:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::PlayAnimation(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<bool>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 13003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::StopAnimation(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 13004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::PauseAnimation(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 13005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::ResumeAnimation(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 13006:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetAnimationSpeed(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 13007:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetAnimationLoop(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 13008:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetAnimationTime(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 13009:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetAnimationTime(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 13010:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetAnimationProgress(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 13011:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetAnimationDuration(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 13012:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsAnimationPlaying(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 13013:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsAnimationPaused(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 13015:
        if(args.size()!=5) throw std::runtime_error("Invalid argument count");
        rt::PlayAnimationBlended(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<bool>(args.at(2)), std::get<double>(args.at(3)), std::get<double>(args.at(4))); return 0.0;
    case 13017:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetAnimationState(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<double>(args.at(2))); return 0.0;
    case 13018:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::SolveTwoBoneIK(std::get<rt::Vec2>(args.at(0)), std::get<rt::Vec2>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3)));
    case 14001:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetMaterial(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 14002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetMaterial(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::ClearMaterial(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 14004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetMaterialColor(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14005:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetMaterialColor(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 14006:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetMaterialOpacity(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14007:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetMaterialOpacity(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 14008:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::ResetMaterialParameters(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 14009:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetMaterialAlphaMode(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14010:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetMaterialAlphaMode(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 14011:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetMaterialAlphaCutoff(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14012:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetMaterialAlphaCutoff(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 14013:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsMaterialUnlit(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14014:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetMaterialUnlit(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 14015:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::MaterialExists(ctx, std::get<std::string>(args.at(0)));
    case 14101:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSprite(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 14102:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSprite(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14103:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::ClearSprite(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 14104:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSpriteFrame(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::int64_t>(args.at(1))); return 0.0;
    case 14105:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSpriteFrame(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14106:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSpriteFrameCount(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14107:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetSpriteFlip(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<bool>(args.at(1)), std::get<bool>(args.at(2))); return 0.0;
    case 14108:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSpriteFlipX(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14109:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSpriteFlipY(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 14110:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SpriteExists(ctx, std::get<std::string>(args.at(0)));
    case 14111:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSpriteState(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 14112:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSpriteState(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 15001:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::CreateCamera(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec3>(args.at(1)));
    case 15002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::HasCamera(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 15003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SetActiveCamera(ctx, std::get<rt::EntityRef>(args.at(0))); return 0.0;
    case 15004:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetActiveCamera(ctx);
    case 15005:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::SetCameraPerspective(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 15006:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::SetCameraOrthographic(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 15007:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetCameraFOV(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 15008:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetCameraFOV(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 15009:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetCameraSize(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 15010:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetCameraSize(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 15011:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetCameraClip(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2))); return 0.0;
    case 15012:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::CameraLookAt(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2))); return 0.0;
    case 15013:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::CameraFollow(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::EntityRef>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 15014:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::WorldToScreen(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec2>(args.at(2)));
    case 15015:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        return rt::ScreenToWorld(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<rt::Vec2>(args.at(1)), std::get<double>(args.at(2)), std::get<rt::Vec2>(args.at(3)));
    case 15016:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::EvaluateCinematicCamera(ctx, std::get<double>(args.at(0)));
    case 17001:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::PlaySound(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<bool>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 17002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::StopSound(ctx, std::get<std::string>(args.at(0))); return 0.0;
    case 17003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::PauseSound(ctx, std::get<std::string>(args.at(0))); return 0.0;
    case 17004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::ResumeSound(ctx, std::get<std::string>(args.at(0))); return 0.0;
    case 17005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsSoundPlaying(ctx, std::get<std::string>(args.at(0)));
    case 17006:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsSoundPaused(ctx, std::get<std::string>(args.at(0)));
    case 17007:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSoundVolume(ctx, std::get<std::string>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 17008:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSoundVolume(ctx, std::get<std::string>(args.at(0)));
    case 17009:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSoundPosition(ctx, std::get<std::string>(args.at(0)));
    case 17010:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSoundDuration(ctx, std::get<std::string>(args.at(0)));
    case 17011:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SoundExists(ctx, std::get<std::string>(args.at(0)));
    case 17012:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        rt::StopAllSounds(ctx); return 0.0;
    case 17013:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SetMasterVolume(ctx, std::get<double>(args.at(0))); return 0.0;
    case 17014:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetMasterVolume(ctx);
    case 18001:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::CreateWidget(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 18002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::DestroyWidget(ctx, std::get<std::string>(args.at(0))); return 0.0;
    case 18003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::WidgetExists(ctx, std::get<std::string>(args.at(0)));
    case 18004:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::ShowWidget(ctx, std::get<std::string>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 18005:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetText(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::string>(args.at(2))); return 0.0;
    case 18006:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetWidgetText(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 18007:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetValue(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<double>(args.at(2))); return 0.0;
    case 18008:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetWidgetValue(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 18009:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetChecked(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<bool>(args.at(2))); return 0.0;
    case 18010:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetWidgetChecked(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 18011:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetEnabled(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<bool>(args.at(2))); return 0.0;
    case 18012:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetWidgetEnabled(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 18013:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetFocus(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 18014:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetStyle(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::string>(args.at(2)), std::get<std::string>(args.at(3))); return 0.0;
    case 18015:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetPosition(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 18016:
        if(args.size()!=4) throw std::runtime_error("Invalid argument count");
        rt::SetWidgetSize(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<double>(args.at(2)), std::get<double>(args.at(3))); return 0.0;
    case 19001:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::FindNavigationPath(ctx, std::get<rt::Vec2>(args.at(0)), std::get<rt::Vec2>(args.at(1)));
    case 19002:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetAIState(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 19003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetAIState(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 19004:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::IsAIState(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 19005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::UpdateWorldStreaming(ctx, std::get<rt::Vec2>(args.at(0)));
    case 20002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetHealth(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 20003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsAlive(ctx, std::get<rt::EntityRef>(args.at(0)));
    case 21001:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::InventoryAddItem(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 21002:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::InventoryRemoveItem(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 21003:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::InventoryCount(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 21004:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::InventoryHasItem(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 21005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::StartQuest(ctx, std::get<std::string>(args.at(0)));
    case 21006:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::AdvanceQuest(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::int64_t>(args.at(2)));
    case 21007:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsQuestActive(ctx, std::get<std::string>(args.at(0)));
    case 21008:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::IsQuestComplete(ctx, std::get<std::string>(args.at(0)));
    case 22001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::SetReplicationAuthority(ctx, std::get<std::string>(args.at(0))); return 0.0;
    case 22002:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetReplicationAuthority(ctx);
    case 22003:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::PublishReplicatedValue(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 22004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetReplicatedValue(ctx, std::get<std::string>(args.at(0)));
    case 22005:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetReplicationRevision(ctx);
    case 23001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::OpenSaveStorage(ctx, std::get<std::string>(args.at(0)));
    case 23002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::CreateSaveSlot(ctx, std::get<std::string>(args.at(0)));
    case 23003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::DeleteSaveSlot(ctx, std::get<std::string>(args.at(0)));
    case 23004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SaveSlotExists(ctx, std::get<std::string>(args.at(0)));
    case 23005:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::ListSaveSlots(ctx);
    case 23006:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SaveVariable(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 23007:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::LoadVariable(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 23008:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::SaveVariables(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::string>>(args.at(1)));
    case 23009:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::LoadVariables(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::string>>(args.at(1)));
    case 23010:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        return rt::SaveJson(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::string>(args.at(2)));
    case 23011:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::LoadJson(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1)));
    case 23012:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSaveVersion(ctx, std::get<std::string>(args.at(0)));
    case 23013:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::ValidateSaveData(ctx, std::get<std::string>(args.at(0)));
    case 23014:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::SaveOperationSucceeded(ctx);
    case 23015:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GetSaveError(ctx);
    case 23016:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::SaveGame(ctx, std::get<std::string>(args.at(0)));
    case 23017:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::LoadGame(ctx, std::get<std::string>(args.at(0)));
    case 23018:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        return rt::GameSavePending(ctx);
    case 26001:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        rt::QuitApplication(ctx); return 0.0;
    case 27001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::Print(ctx, std::get<std::string>(args.at(0))); return 0.0;
    case 27002:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::Assert(ctx, std::get<bool>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 27003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        rt::BeginProfileSample(ctx, std::get<std::string>(args.at(0))); return 0.0;
    case 27004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::EndProfileSample(ctx, std::get<std::string>(args.at(0)));
    case 27005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetProfileSample(ctx, std::get<std::string>(args.at(0)));
    case 27006:
        if(args.size()!=0) throw std::runtime_error("Invalid argument count");
        rt::EmbeddedCode(ctx); return 0.0;
    case 50000:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<double>(ctx, std::get<std::string>(args.at(0)));
    case 50001:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<std::int64_t>(ctx, std::get<std::string>(args.at(0)));
    case 50002:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<bool>(ctx, std::get<std::string>(args.at(0)));
    case 50003:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<std::string>(ctx, std::get<std::string>(args.at(0)));
    case 50004:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Vec3>(ctx, std::get<std::string>(args.at(0)));
    case 50005:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::EntityRef>(ctx, std::get<std::string>(args.at(0)));
    case 50006:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Vec2>(ctx, std::get<std::string>(args.at(0)));
    case 50007:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Vec4>(ctx, std::get<std::string>(args.at(0)));
    case 50008:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Quat>(ctx, std::get<std::string>(args.at(0)));
    case 50009:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Mat4>(ctx, std::get<std::string>(args.at(0)));
    case 50010:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<double>(ctx, std::get<std::string>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 50011:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<std::int64_t>(ctx, std::get<std::string>(args.at(0)), std::get<std::int64_t>(args.at(1))); return 0.0;
    case 50012:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<bool>(ctx, std::get<std::string>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 50013:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<std::string>(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 50014:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Vec3>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 50015:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::EntityRef>(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1))); return 0.0;
    case 50016:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Vec2>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec2>(args.at(1))); return 0.0;
    case 50017:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Vec4>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec4>(args.at(1))); return 0.0;
    case 50018:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Quat>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Quat>(args.at(1))); return 0.0;
    case 50019:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Mat4>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Mat4>(args.at(1))); return 0.0;
    case 50020:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<double>>(ctx, std::get<std::string>(args.at(0)));
    case 50021:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 50022:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 50023:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 50024:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 50025:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 50026:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 50027:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 50028:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 50029:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 50030:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<double>>(args.at(1))); return 0.0;
    case 50031:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::int64_t>>(args.at(1))); return 0.0;
    case 50032:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<bool>>(args.at(1))); return 0.0;
    case 50033:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::string>>(args.at(1))); return 0.0;
    case 50034:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec3>>(args.at(1))); return 0.0;
    case 50035:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::EntityRef>>(args.at(1))); return 0.0;
    case 50036:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec2>>(args.at(1))); return 0.0;
    case 50037:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec4>>(args.at(1))); return 0.0;
    case 50038:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Quat>>(args.at(1))); return 0.0;
    case 50039:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Mat4>>(args.at(1))); return 0.0;
    case 50040:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<double>>(ctx, std::get<std::string>(args.at(0)));
    case 50041:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 50042:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 50043:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 50044:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 50045:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 50046:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 50047:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 50048:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 50049:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 50050:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<double>>(args.at(1))); return 0.0;
    case 50051:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<std::int64_t>>(args.at(1))); return 0.0;
    case 50052:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<bool>>(args.at(1))); return 0.0;
    case 50053:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<std::string>>(args.at(1))); return 0.0;
    case 50054:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec3>>(args.at(1))); return 0.0;
    case 50055:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::EntityRef>>(args.at(1))); return 0.0;
    case 50056:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec2>>(args.at(1))); return 0.0;
    case 50057:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec4>>(args.at(1))); return 0.0;
    case 50058:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Quat>>(args.at(1))); return 0.0;
    case 50059:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Mat4>>(args.at(1))); return 0.0;
    case 50060:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<double>>(ctx, std::get<std::string>(args.at(0)));
    case 50061:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 50062:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 50063:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 50064:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 50065:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 50066:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 50067:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 50068:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 50069:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetGlobalVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 50070:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<double>>(args.at(1))); return 0.0;
    case 50071:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<std::int64_t>>(args.at(1))); return 0.0;
    case 50072:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<bool>>(args.at(1))); return 0.0;
    case 50073:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<std::string>>(args.at(1))); return 0.0;
    case 50074:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec3>>(args.at(1))); return 0.0;
    case 50075:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::EntityRef>>(args.at(1))); return 0.0;
    case 50076:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec2>>(args.at(1))); return 0.0;
    case 50077:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec4>>(args.at(1))); return 0.0;
    case 50078:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Quat>>(args.at(1))); return 0.0;
    case 50079:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetGlobalVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Mat4>>(args.at(1))); return 0.0;
    case 50080:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<double>(ctx, std::get<std::string>(args.at(0)));
    case 50081:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<std::int64_t>(ctx, std::get<std::string>(args.at(0)));
    case 50082:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<bool>(ctx, std::get<std::string>(args.at(0)));
    case 50083:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<std::string>(ctx, std::get<std::string>(args.at(0)));
    case 50084:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Vec3>(ctx, std::get<std::string>(args.at(0)));
    case 50085:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::EntityRef>(ctx, std::get<std::string>(args.at(0)));
    case 50086:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Vec2>(ctx, std::get<std::string>(args.at(0)));
    case 50087:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Vec4>(ctx, std::get<std::string>(args.at(0)));
    case 50088:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Quat>(ctx, std::get<std::string>(args.at(0)));
    case 50089:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Mat4>(ctx, std::get<std::string>(args.at(0)));
    case 50090:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<double>(ctx, std::get<std::string>(args.at(0)), std::get<double>(args.at(1))); return 0.0;
    case 50091:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<std::int64_t>(ctx, std::get<std::string>(args.at(0)), std::get<std::int64_t>(args.at(1))); return 0.0;
    case 50092:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<bool>(ctx, std::get<std::string>(args.at(0)), std::get<bool>(args.at(1))); return 0.0;
    case 50093:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<std::string>(ctx, std::get<std::string>(args.at(0)), std::get<std::string>(args.at(1))); return 0.0;
    case 50094:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Vec3>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec3>(args.at(1))); return 0.0;
    case 50095:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::EntityRef>(ctx, std::get<std::string>(args.at(0)), std::get<rt::EntityRef>(args.at(1))); return 0.0;
    case 50096:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Vec2>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec2>(args.at(1))); return 0.0;
    case 50097:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Vec4>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Vec4>(args.at(1))); return 0.0;
    case 50098:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Quat>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Quat>(args.at(1))); return 0.0;
    case 50099:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Mat4>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Mat4>(args.at(1))); return 0.0;
    case 50100:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<double>>(ctx, std::get<std::string>(args.at(0)));
    case 50101:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 50102:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 50103:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 50104:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 50105:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 50106:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 50107:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 50108:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 50109:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 50110:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<double>>(args.at(1))); return 0.0;
    case 50111:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::int64_t>>(args.at(1))); return 0.0;
    case 50112:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<bool>>(args.at(1))); return 0.0;
    case 50113:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<std::string>>(args.at(1))); return 0.0;
    case 50114:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec3>>(args.at(1))); return 0.0;
    case 50115:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::EntityRef>>(args.at(1))); return 0.0;
    case 50116:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec2>>(args.at(1))); return 0.0;
    case 50117:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Vec4>>(args.at(1))); return 0.0;
    case 50118:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Quat>>(args.at(1))); return 0.0;
    case 50119:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Array<rt::Mat4>>(args.at(1))); return 0.0;
    case 50120:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<double>>(ctx, std::get<std::string>(args.at(0)));
    case 50121:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 50122:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 50123:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 50124:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 50125:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 50126:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 50127:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 50128:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 50129:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 50130:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<double>>(args.at(1))); return 0.0;
    case 50131:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<std::int64_t>>(args.at(1))); return 0.0;
    case 50132:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<bool>>(args.at(1))); return 0.0;
    case 50133:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<std::string>>(args.at(1))); return 0.0;
    case 50134:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec3>>(args.at(1))); return 0.0;
    case 50135:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::EntityRef>>(args.at(1))); return 0.0;
    case 50136:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec2>>(args.at(1))); return 0.0;
    case 50137:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Vec4>>(args.at(1))); return 0.0;
    case 50138:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Quat>>(args.at(1))); return 0.0;
    case 50139:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Map<rt::Mat4>>(args.at(1))); return 0.0;
    case 50140:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<double>>(ctx, std::get<std::string>(args.at(0)));
    case 50141:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<std::int64_t>>(ctx, std::get<std::string>(args.at(0)));
    case 50142:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<bool>>(ctx, std::get<std::string>(args.at(0)));
    case 50143:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<std::string>>(ctx, std::get<std::string>(args.at(0)));
    case 50144:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)));
    case 50145:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)));
    case 50146:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)));
    case 50147:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)));
    case 50148:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<rt::Quat>>(ctx, std::get<std::string>(args.at(0)));
    case 50149:
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        return rt::GetSceneVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)));
    case 50150:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<double>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<double>>(args.at(1))); return 0.0;
    case 50151:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<std::int64_t>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<std::int64_t>>(args.at(1))); return 0.0;
    case 50152:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<bool>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<bool>>(args.at(1))); return 0.0;
    case 50153:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<std::string>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<std::string>>(args.at(1))); return 0.0;
    case 50154:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec3>>(args.at(1))); return 0.0;
    case 50155:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::EntityRef>>(args.at(1))); return 0.0;
    case 50156:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec2>>(args.at(1))); return 0.0;
    case 50157:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Vec4>>(args.at(1))); return 0.0;
    case 50158:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<rt::Quat>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Quat>>(args.at(1))); return 0.0;
    case 50159:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        rt::SetSceneVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<std::string>(args.at(0)), std::get<rt::Set<rt::Mat4>>(args.at(1))); return 0.0;
    case 50160:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<double>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50161:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<std::int64_t>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50162:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<bool>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50163:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<std::string>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50164:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Vec3>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50165:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::EntityRef>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50166:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Vec2>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50167:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Vec4>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50168:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Quat>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50169:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Mat4>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50170:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<double>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<double>(args.at(2))); return 0.0;
    case 50171:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<std::int64_t>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::int64_t>(args.at(2))); return 0.0;
    case 50172:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<bool>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<bool>(args.at(2))); return 0.0;
    case 50173:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<std::string>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<std::string>(args.at(2))); return 0.0;
    case 50174:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Vec3>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Vec3>(args.at(2))); return 0.0;
    case 50175:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::EntityRef>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::EntityRef>(args.at(2))); return 0.0;
    case 50176:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Vec2>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Vec2>(args.at(2))); return 0.0;
    case 50177:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Vec4>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Vec4>(args.at(2))); return 0.0;
    case 50178:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Quat>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Quat>(args.at(2))); return 0.0;
    case 50179:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Mat4>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Mat4>(args.at(2))); return 0.0;
    case 50180:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<double>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50181:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<std::int64_t>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50182:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<bool>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50183:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<std::string>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50184:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50185:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50186:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50187:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50188:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<rt::Quat>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50189:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50190:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<double>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<double>>(args.at(2))); return 0.0;
    case 50191:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<std::int64_t>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<std::int64_t>>(args.at(2))); return 0.0;
    case 50192:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<bool>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<bool>>(args.at(2))); return 0.0;
    case 50193:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<std::string>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<std::string>>(args.at(2))); return 0.0;
    case 50194:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<rt::Vec3>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<rt::Vec3>>(args.at(2))); return 0.0;
    case 50195:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<rt::EntityRef>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<rt::EntityRef>>(args.at(2))); return 0.0;
    case 50196:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<rt::Vec2>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<rt::Vec2>>(args.at(2))); return 0.0;
    case 50197:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<rt::Vec4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<rt::Vec4>>(args.at(2))); return 0.0;
    case 50198:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<rt::Quat>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<rt::Quat>>(args.at(2))); return 0.0;
    case 50199:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Array<rt::Mat4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Array<rt::Mat4>>(args.at(2))); return 0.0;
    case 50200:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<double>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50201:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<std::int64_t>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50202:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<bool>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50203:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<std::string>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50204:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50205:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50206:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50207:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50208:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<rt::Quat>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50209:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50210:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<double>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<double>>(args.at(2))); return 0.0;
    case 50211:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<std::int64_t>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<std::int64_t>>(args.at(2))); return 0.0;
    case 50212:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<bool>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<bool>>(args.at(2))); return 0.0;
    case 50213:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<std::string>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<std::string>>(args.at(2))); return 0.0;
    case 50214:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<rt::Vec3>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<rt::Vec3>>(args.at(2))); return 0.0;
    case 50215:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<rt::EntityRef>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<rt::EntityRef>>(args.at(2))); return 0.0;
    case 50216:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<rt::Vec2>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<rt::Vec2>>(args.at(2))); return 0.0;
    case 50217:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<rt::Vec4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<rt::Vec4>>(args.at(2))); return 0.0;
    case 50218:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<rt::Quat>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<rt::Quat>>(args.at(2))); return 0.0;
    case 50219:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Map<rt::Mat4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Map<rt::Mat4>>(args.at(2))); return 0.0;
    case 50220:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<double>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50221:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<std::int64_t>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50222:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<bool>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50223:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<std::string>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50224:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50225:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50226:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50227:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50228:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<rt::Quat>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50229:
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        return rt::GetEntityVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)));
    case 50230:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<double>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<double>>(args.at(2))); return 0.0;
    case 50231:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<std::int64_t>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<std::int64_t>>(args.at(2))); return 0.0;
    case 50232:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<bool>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<bool>>(args.at(2))); return 0.0;
    case 50233:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<std::string>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<std::string>>(args.at(2))); return 0.0;
    case 50234:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<rt::Vec3>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<rt::Vec3>>(args.at(2))); return 0.0;
    case 50235:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<rt::EntityRef>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<rt::EntityRef>>(args.at(2))); return 0.0;
    case 50236:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<rt::Vec2>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<rt::Vec2>>(args.at(2))); return 0.0;
    case 50237:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<rt::Vec4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<rt::Vec4>>(args.at(2))); return 0.0;
    case 50238:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<rt::Quat>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<rt::Quat>>(args.at(2))); return 0.0;
    case 50239:
        if(args.size()!=3) throw std::runtime_error("Invalid argument count");
        rt::SetEntityVariableAs<rt::Set<rt::Mat4>>(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<std::string>(args.at(1)), std::get<rt::Set<rt::Mat4>>(args.at(2))); return 0.0;
    default: return type<0 || (type>=800000 && type<900000) ? DispatchUserVariable(ctx,type,args) : DispatchComponent(ctx,type,args);
    }
}
std::vector<Value> dispatch_results(Ctx& ctx, int type, const std::vector<Value>& args) {
    switch(type) {
    case 5100: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<double>(ctx, std::get<rt::Array<double>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5101: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<std::int64_t>(ctx, std::get<rt::Array<std::int64_t>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5102: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<bool>(ctx, std::get<rt::Array<bool>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5103: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<std::string>(ctx, std::get<rt::Array<std::string>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5104: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<rt::Vec3>(ctx, std::get<rt::Array<rt::Vec3>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5105: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<rt::EntityRef>(ctx, std::get<rt::Array<rt::EntityRef>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5106: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<rt::Vec2>(ctx, std::get<rt::Array<rt::Vec2>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5107: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<rt::Vec4>(ctx, std::get<rt::Array<rt::Vec4>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5108: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<rt::Quat>(ctx, std::get<rt::Array<rt::Quat>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5109: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomItem<rt::Mat4>(ctx, std::get<rt::Array<rt::Mat4>>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5110: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<double>(ctx, std::get<rt::Array<double>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5111: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<std::int64_t>(ctx, std::get<rt::Array<std::int64_t>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5112: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<bool>(ctx, std::get<rt::Array<bool>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5113: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<std::string>(ctx, std::get<rt::Array<std::string>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5114: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<rt::Vec3>(ctx, std::get<rt::Array<rt::Vec3>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5115: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<rt::EntityRef>(ctx, std::get<rt::Array<rt::EntityRef>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5116: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<rt::Vec2>(ctx, std::get<rt::Array<rt::Vec2>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5117: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<rt::Vec4>(ctx, std::get<rt::Array<rt::Vec4>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5118: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<rt::Quat>(ctx, std::get<rt::Array<rt::Quat>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 5119: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::RandomWeightedItem<rt::Mat4>(ctx, std::get<rt::Array<rt::Mat4>>(args.at(0)), std::get<rt::Array<double>>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    case 11031: {
        if(args.size()!=5) throw std::runtime_error("Invalid argument count");
        auto result = rt::PhysicsRaycastHit(ctx, std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<std::int64_t>(args.at(2)), std::get<bool>(args.at(3)), std::get<rt::EntityRef>(args.at(4)));
        return {std::get<0>(result), std::get<1>(result), std::get<2>(result), std::get<3>(result), std::get<4>(result), std::get<5>(result)};
    }
    case 11032: {
        if(args.size()!=6) throw std::runtime_error("Invalid argument count");
        auto result = rt::PhysicsSphereCast(ctx, std::get<rt::Vec3>(args.at(0)), std::get<double>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<std::int64_t>(args.at(3)), std::get<bool>(args.at(4)), std::get<rt::EntityRef>(args.at(5)));
        return {std::get<0>(result), std::get<1>(result), std::get<2>(result), std::get<3>(result), std::get<4>(result), std::get<5>(result)};
    }
    case 11033: {
        if(args.size()!=7) throw std::runtime_error("Invalid argument count");
        auto result = rt::PhysicsBoxCast(ctx, std::get<rt::Vec3>(args.at(0)), std::get<rt::Vec3>(args.at(1)), std::get<rt::Vec3>(args.at(2)), std::get<rt::Vec3>(args.at(3)), std::get<std::int64_t>(args.at(4)), std::get<bool>(args.at(5)), std::get<rt::EntityRef>(args.at(6)));
        return {std::get<0>(result), std::get<1>(result), std::get<2>(result), std::get<3>(result), std::get<4>(result), std::get<5>(result)};
    }
    case 11034: {
        if(args.size()!=8) throw std::runtime_error("Invalid argument count");
        auto result = rt::PhysicsCapsuleCast(ctx, std::get<rt::Vec3>(args.at(0)), std::get<double>(args.at(1)), std::get<double>(args.at(2)), std::get<rt::Vec3>(args.at(3)), std::get<rt::Vec3>(args.at(4)), std::get<std::int64_t>(args.at(5)), std::get<bool>(args.at(6)), std::get<rt::EntityRef>(args.at(7)));
        return {std::get<0>(result), std::get<1>(result), std::get<2>(result), std::get<3>(result), std::get<4>(result), std::get<5>(result)};
    }
    case 12008: {
        if(args.size()!=1) throw std::runtime_error("Invalid argument count");
        auto result = rt::CharacterGroundCheck(ctx, std::get<rt::EntityRef>(args.at(0)));
        return {std::get<0>(result), std::get<1>(result), std::get<2>(result), std::get<3>(result), std::get<4>(result), std::get<5>(result)};
    }
    case 20001: {
        if(args.size()!=2) throw std::runtime_error("Invalid argument count");
        auto result = rt::ApplyDamage(ctx, std::get<rt::EntityRef>(args.at(0)), std::get<double>(args.at(1)));
        return {std::get<0>(result), std::get<1>(result)};
    }
    default: return {dispatch(ctx,type,args)};
    }
}
}
namespace rt { bool IsInputButton(const std::string& button) {
    static const std::set<std::string> buttons = {std::string("A", 1),std::string("B", 1),std::string("C", 1),std::string("D", 1),std::string("E", 1),std::string("F", 1),std::string("G", 1),std::string("H", 1),std::string("I", 1),std::string("J", 1),std::string("K", 1),std::string("L", 1),std::string("M", 1),std::string("N", 1),std::string("O", 1),std::string("P", 1),std::string("Q", 1),std::string("R", 1),std::string("S", 1),std::string("T", 1),std::string("U", 1),std::string("V", 1),std::string("W", 1),std::string("X", 1),std::string("Y", 1),std::string("Z", 1),std::string("0", 1),std::string("1", 1),std::string("2", 1),std::string("3", 1),std::string("4", 1),std::string("5", 1),std::string("6", 1),std::string("7", 1),std::string("8", 1),std::string("9", 1),std::string("Space", 5),std::string("Return", 6),std::string("Escape", 6),std::string("Tab", 3),std::string("Backspace", 9),std::string("Delete", 6),std::string("Insert", 6),std::string("Home", 4),std::string("End", 3),std::string("PageUp", 6),std::string("PageDown", 8),std::string("Left", 4),std::string("Right", 5),std::string("Up", 2),std::string("Down", 4),std::string("Left Shift", 10),std::string("Right Shift", 11),std::string("Left Ctrl", 9),std::string("Right Ctrl", 10),std::string("Left Alt", 8),std::string("Right Alt", 9),std::string("CapsLock", 8),std::string("Numlock", 7),std::string("ScrollLock", 10),std::string("PrintScreen", 11),std::string("Pause", 5),std::string("-", 1),std::string("=", 1),std::string("[", 1),std::string("]", 1),std::string("\\", 1),std::string(";", 1),std::string("'", 1),std::string(",", 1),std::string(".", 1),std::string("/", 1),std::string("`", 1),std::string("F1", 2),std::string("F2", 2),std::string("F3", 2),std::string("F4", 2),std::string("F5", 2),std::string("F6", 2),std::string("F7", 2),std::string("F8", 2),std::string("F9", 2),std::string("F10", 3),std::string("F11", 3),std::string("F12", 3),std::string("F13", 3),std::string("F14", 3),std::string("F15", 3),std::string("F16", 3),std::string("F17", 3),std::string("F18", 3),std::string("F19", 3),std::string("F20", 3),std::string("F21", 3),std::string("F22", 3),std::string("F23", 3),std::string("F24", 3),std::string("MouseLeft", 9),std::string("MouseRight", 10),std::string("MouseMiddle", 11),std::string("MouseX1", 7),std::string("MouseX2", 7)};
    return buttons.contains(button);
}
const std::vector<std::string> GamepadAxisNames = {std::string("LeftX", 5),std::string("LeftY", 5),std::string("RightX", 6),std::string("RightY", 6),std::string("LeftTrigger", 11),std::string("RightTrigger", 12)};
const std::vector<std::string> GamepadButtonNames = {std::string("South", 5),std::string("East", 4),std::string("West", 4),std::string("North", 5),std::string("Back", 4),std::string("Guide", 5),std::string("Start", 5),std::string("LeftStick", 9),std::string("RightStick", 10),std::string("LeftShoulder", 12),std::string("RightShoulder", 13),std::string("DpadUp", 6),std::string("DpadDown", 8),std::string("DpadLeft", 8),std::string("DpadRight", 9),std::string("Misc1", 5),std::string("RightPaddle1", 12),std::string("LeftPaddle1", 11),std::string("RightPaddle2", 12),std::string("LeftPaddle2", 11),std::string("Touchpad", 8),std::string("Misc2", 5),std::string("Misc3", 5),std::string("Misc4", 5),std::string("Misc5", 5),std::string("Misc6", 5)};
}
