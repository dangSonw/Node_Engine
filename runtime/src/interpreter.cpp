#include "node_code.hpp"
namespace rt {
std::vector<Value> Invoke(Ctx& c, int function, std::vector<Value> args) {
    CallDepthScope depth(c);
    struct Frame {
        Ctx& c;
        decltype(Ctx::locals) locals;
        std::vector<Value> parameters;
        explicit Frame(Ctx& ctx):c(ctx),locals(std::move(c.locals)),parameters(std::move(c.parameters)) {
            c.locals.clear(); c.parameters.clear();
        }
        ~Frame() { c.locals=std::move(locals); c.parameters=std::move(parameters); }
    } frame(c);
    c.parameters=std::move(args);
    const auto& definition=c.functions.at(std::to_string(function));
    if(c.parameters.size()!=definition.at("inputs").size()) throw std::runtime_error("Function argument count mismatch");
    for(std::size_t i=0;i<c.parameters.size();++i)
        ValidateTypedValue(c,definition.at("inputs").at(i).at("type").get<std::string>(),c.parameters[i]);
    auto result=Execute(c,definition.at("body"));
    if(!result || result->size()!=definition.at("outputs").size()) throw std::runtime_error("Function did not return its declared results");
    for(std::size_t i=0;i<result->size();++i)
        ValidateTypedValue(c,definition.at("outputs").at(i).at("type").get<std::string>(),result->at(i));
    return std::move(*result);
}
Value Evaluate(Ctx& c, const Json& expr) {
    if(expr.at("op")=="literal") {
        return CheckedValueFromJson(c,expr.at("type").get<std::string>(),expr.at("value"));
    }
    if(expr.at("op")=="local") {
        auto key=std::pair{expr.at("node").get<std::string>(),expr.at("port").get<std::string>()};
        auto found=c.locals.find(key);
        if(found==c.locals.end()) throw std::runtime_error("Output outside its execution scope");
        return found->second;
    }
    if(expr.at("op")=="parameter") return c.parameters.at(expr.at("index").get<std::size_t>());
    if(expr.at("op")=="select") {
        const auto& args=expr.at("args");
        if(!args.is_array() || args.size()!=3) throw std::runtime_error("Select requires three arguments");
        const auto condition=std::get<bool>(Evaluate(c,args.at(0)));
        Tick(c,expr.at("node").get<std::string>());
        return SelectValue(condition,[&]{return Evaluate(c,args.at(1));},[&]{return Evaluate(c,args.at(2));});
    }
    std::vector<Value> values;
    for(const auto& arg:expr.at("args")) values.push_back(Evaluate(c,arg));
    Tick(c,expr.at("node").get<std::string>());
    if(expr.at("op")=="invoke") return Invoke(c,expr.at("type").get<int>(),std::move(values)).at(expr.at("index").get<std::size_t>());
    const auto op=expr.at("op").get<std::string>();
    if(op=="struct_make") {
        auto fields=Json::object(); const auto& names=expr.at("fields");
        if(names.size()!=values.size()) throw std::runtime_error("Struct argument count mismatch");
        for(std::size_t i=0;i<values.size();++i)
            fields[names.at(i).get<std::string>()]=std::visit([](const auto& item){return ToJson(item);},values.at(i));
        return CheckedValueFromJson(c,expr.at("type").get<std::string>(),fields);
    }
    if(op=="enum_value") return CheckedValueFromJson(c,expr.at("type").get<std::string>(),std::get<std::string>(values.at(0)));
    if(op=="struct_get") return ReadStructField(c,std::get<StructValue>(values.at(0)),expr.at("field").get<std::string>(),expr.at("type").get<std::string>());
    if(op=="collection_callback") {
        auto items=IterationValues(values.at(0));
        const auto callback=expr.at("callback").get<int>();
        const auto mode=expr.at("mode").get<std::string>();
        auto invoke=[&](const Value& item) {
            auto result=Invoke(c,callback,{item});
            if(result.size()!=1) throw std::runtime_error("Collection callback requires one result");
            return std::move(result.front());
        };
        if(mode=="SortArray") std::stable_sort(items.begin(),items.end(),[&](const Value& a,const Value& b) {
            return std::get<double>(invoke(a))<std::get<double>(invoke(b));
        });
        auto result=Json::array();
        for(const auto& item:items) {
            if(mode=="FilterArray" && !std::get<bool>(invoke(item))) continue;
            const auto mapped=mode=="MapArray" ? invoke(item) : item;
            result.push_back(std::visit([](const auto& value){return ToJson(value);},mapped));
        }
        if(mode!="SortArray" && mode!="FilterArray" && mode!="MapArray") throw std::runtime_error("Unknown collection callback mode");
        return CheckedValueFromJson(c,expr.at("type").get<std::string>(),result);
    }
    return dispatch(c,expr.at("type").get<int>(),values);
}
namespace {
enum class Control { Next, Return, Break, Continue };
struct ExecutionResult { Control control=Control::Next; std::vector<Value> values; };
ExecutionResult ExecuteBlock(Ctx& c,const Json& statements,int loop_depth) {
    ExecutionScope execution(c);
    for(const auto& s:statements) {
        const auto op=s.at("op").get<std::string>();
        const auto node=s.at("node").get<std::string>();
        if(op=="continuation_entry") {
            CapturedValues captures;
            for(const auto& p:s.at("captures")) {
                auto key=std::pair{p.at("node").get<std::string>(),p.at("port").get<std::string>()};
                captures.emplace(key,c.locals.at(key));
            }
            StartContinuation(c,s.at("entry").get<std::size_t>(),std::move(captures)); continue;
        }
        if(op=="while") {
            while(true) {
                const bool condition=std::get<bool>(Evaluate(c,s.at("args").at(0)));
                Tick(c,node);
                if(!condition) break;
                auto result=ExecuteBlock(c,s.at("body"),loop_depth+1);
                if(result.control==Control::Return) return result;
                if(result.control==Control::Break) break;
            }
            continue;
        }
        std::vector<Value> args;
        for(const auto& arg:s.at("args")) args.push_back(Evaluate(c,arg));
        Tick(c,node);
        if(op=="return") return {Control::Return,std::move(args)};
        if(op=="break" || op=="continue") {
            if(loop_depth==0 || !args.empty()) throw std::runtime_error("Loop control requires a loop Body in this graph and no arguments");
            return {op=="break" ? Control::Break : Control::Continue,{}};
        }
        if(op=="flow") {
            const auto selected=DispatchFlow(c,s.at("type").get<int>(),node,s.at("input").get<std::string>(),args);
            if(selected.branch>=0) {
                struct Scope {
                    Ctx& c; std::string node;
                    ~Scope() { c.locals.erase({node,"Counter"}); c.locals.erase({node,"Is A"}); c.locals.erase({node,"Index"}); }
                } scope{c,node};
                c.locals[{node,"Counter"}]=selected.count; c.locals[{node,"Is A"}]=selected.is_a;
                c.locals[{node,"Index"}]=selected.index;
                auto result=ExecuteBlock(c,s.at("branches").at(selected.branch),loop_depth);
                if(result.control!=Control::Next) return result;
            }
        } else if(op=="function_call") {
            auto results=Invoke(c,s.at("type").get<int>(),std::move(args));
            for(std::size_t i=0;i<results.size();++i) c.locals[{node,s.at("outputs").at(i).get<std::string>()}]=std::move(results[i]);
        } else if(op=="action_result") {
            const auto code=s.value("code",std::string{});
            auto results=code.empty() ? dispatch_results(c,s.at("type").get<int>(),args)
                                     : RunNodeCode(c,s.at("type").get<int>(),node,code,args);
            const auto& outputs=s.at("outputs");
            if(!outputs.is_array() || outputs.size()!=results.size()) throw std::runtime_error("Action result count mismatch");
            for(std::size_t i=0;i<results.size();++i) c.locals[{node,outputs.at(i).get<std::string>()}]=std::move(results[i]);
        }
        else if(op=="action") {
            const auto code=s.value("code",std::string{});
            if(code.empty()) dispatch(c,s.at("type").get<int>(),args);
            else RunNodeCode(c,s.at("type").get<int>(),node,code,args);
        }
        else if(op=="emit_event") SendEvent(c,s.at("event").get<int>(),std::get<EntityRef>(args.at(0)),std::get<EntityRef>(args.at(1)),std::vector<Value>(args.begin()+2,args.end()));
        else if(op=="broadcast_event") BroadcastEvent(c,s.at("event").get<int>(),std::get<EntityRef>(args.at(0)),std::vector<Value>(args.begin()+1,args.end()));
        else if(op=="subscribe_event" || op=="unsubscribe_event") SetEventSubscription(c,s.at("event").get<int>(),std::get<EntityRef>(args.at(0)),op=="subscribe_event");
        else if(op=="switch") {
            if(args.size()!=1 || s.at("branches").size()!=s.at("cases").size()+1) throw std::runtime_error("Invalid Switch branches");
            auto result=ExecuteBlock(c,s.at("branches").at(DispatchSwitch(args.at(0),s.at("cases"))),loop_depth);
            if(result.control!=Control::Next) return result;
        }
        else if(op=="branch") {
            auto result=ExecuteBlock(c,s.at(std::get<bool>(args.at(0)) ? "yes" : "no"),loop_depth);
            if(result.control!=Control::Next) return result;
        }
        else if(op=="for") {
            const int count=LoopCount(std::get<double>(args.at(0)));
            for(int i=0;i<count;++i) {
                Tick(c,node);
                auto result=ExecuteBlock(c,s.at("body"),loop_depth+1);
                if(result.control==Control::Return) return result;
                if(result.control==Control::Break) break;
            }
        } else if(op=="foreach") {
            auto values=IterationValues(args.at(0)); // Snapshot once; body edits cannot invalidate traversal.
            auto keys=IterationKeys(args.at(0));
            struct Scope {
                Ctx& c; std::string node;
                ~Scope() { c.locals.erase({node,"Key"}); c.locals.erase({node,"Item"}); c.locals.erase({node,"Index"}); }
            } scope{c,node};
            for(std::size_t i=0;i<values.size();++i) {
                Tick(c,node);
                if(!keys.empty()) c.locals[{node,"Key"}]=keys.at(i);
                c.locals[{node,"Item"}]=values[i];
                c.locals[{node,"Index"}]=static_cast<std::int64_t>(i);
                auto result=ExecuteBlock(c,s.at("body"),loop_depth+1);
                if(result.control==Control::Return) return result;
                if(result.control==Control::Break) break;
            }
        } else throw std::runtime_error("Unknown IR statement: "+op);
    }
    return {};
}
}
std::optional<std::vector<Value>> Execute(Ctx& c,const Json& statements) {
    auto result=ExecuteBlock(c,statements,0);
    if(result.control==Control::Return) return std::move(result.values);
    return std::nullopt;
}
}
