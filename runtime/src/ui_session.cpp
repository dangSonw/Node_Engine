#include "ui_session.hpp"
#include <RmlUi/Core.h>
#include <RmlUi/Core/Elements/ElementFormControl.h>
#include <RmlUi/Core/Elements/ElementFormControlInput.h>
#include <RmlUi/Core/Elements/ElementFormControlTextArea.h>
#include <RmlUi/Core/Elements/ElementFormControlSelect.h>
#include <RmlUi/Core/Elements/ElementProgress.h>
#include <RmlUi/Core/ElementInstancer.h>
#include <RmlUi_Platform_SDL.h>
#include <SDL3_image/SDL_image.h>
#include <algorithm>
#include <cmath>
#include <map>
#include <set>
#include <stdexcept>

// The context root has no owner document, so public Element::Focus() cannot
// focus it. Dispatch normal blur events, then clear only the root focus chain;
// each document retains its own saved focus leaf for later reactivation.
bool Rml::Context::ClearCheckpointFocus() {
    if(!OnFocusChange(root.get(),false)) return false;
    root->focus=nullptr; return true;
}

namespace rt {
namespace {
void require(bool ok,const std::string& message) { if(!ok) throw std::runtime_error(message); }
void identifier(const std::string& id) {
    require(!id.empty() && id.size()<=128 && id.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")==std::string::npos,
        "UI names must contain 1-128 letters, digits, underscores or hyphens");
}
struct NullRenderer: Rml::RenderInterface {
    Rml::CompiledGeometryHandle CompileGeometry(Rml::Span<const Rml::Vertex>,Rml::Span<const int>) override { return 1; }
    void RenderGeometry(Rml::CompiledGeometryHandle,Rml::Vector2f,Rml::TextureHandle) override {}
    void ReleaseGeometry(Rml::CompiledGeometryHandle) override {}
    Rml::TextureHandle LoadTexture(Rml::Vector2i& dimensions,const Rml::String& source) override {
        Rml::String data;
        if(!Rml::GetFileInterface()->LoadFile(source,data)) return 0;
        auto* image=IMG_Load_IO(SDL_IOFromConstMem(data.data(),data.size()),true);
        if(!image) return 0;
        dimensions={image->w,image->h}; SDL_DestroySurface(image); return 1;
    }
    Rml::TextureHandle GenerateTexture(Rml::Span<const Rml::byte>,Rml::Vector2i) override { return 1; }
    void ReleaseTexture(Rml::TextureHandle) override {}
    void EnableScissorRegion(bool) override {}
    void SetScissorRegion(Rml::Rectanglei) override {}
};
struct Files: Rml::FileInterface {
    std::filesystem::path assets;
    Rml::FileHandle Open(const Rml::String& path) override {
        try {
            const auto resolved=std::filesystem::canonical(std::filesystem::u8path(path));
            if(!assets.empty()) {
                const auto relative=resolved.lexically_relative(assets);
                if(relative.empty() || relative.is_absolute()) return 0;
                for(const auto& p:relative) if(p=="..") return 0;
            }
            if(std::filesystem::file_size(resolved)>64*1024*1024) return 0;
            return reinterpret_cast<Rml::FileHandle>(SDL_IOFromFile(path.c_str(),"rb"));
        } catch(const std::exception&) { return 0; }
    }
    void Close(Rml::FileHandle file) override { SDL_CloseIO(reinterpret_cast<SDL_IOStream*>(file)); }
    size_t Read(void* buffer,size_t bytes,Rml::FileHandle file) override { return SDL_ReadIO(reinterpret_cast<SDL_IOStream*>(file),buffer,bytes); }
    bool Seek(Rml::FileHandle file,long offset,int origin) override {
        const auto whence=origin==SEEK_SET ? SDL_IO_SEEK_SET : origin==SEEK_CUR ? SDL_IO_SEEK_CUR : SDL_IO_SEEK_END;
        return SDL_SeekIO(reinterpret_cast<SDL_IOStream*>(file),offset,whence)>=0;
    }
    size_t Tell(Rml::FileHandle file) override { return static_cast<size_t>(SDL_TellIO(reinterpret_cast<SDL_IOStream*>(file))); }
};
// Staged contexts record window requests until the whole game can commit.
struct Platform: SystemInterface_SDL {
    bool active,keyboard=false;
    Rml::Vector2f caret{};
    float line_height=0;
    Rml::String cursor;
    Platform(SDL_Window* window,bool enabled):SystemInterface_SDL(window),active(enabled) {}
    void SetMouseCursor(const Rml::String& name) override {
        cursor=name; if(active) SystemInterface_SDL::SetMouseCursor(name);
    }
    void ActivateKeyboard(Rml::Vector2f position,float height) override {
        keyboard=true; caret=position; line_height=height;
        if(active) SystemInterface_SDL::ActivateKeyboard(position,height);
    }
    void DeactivateKeyboard() override {
        keyboard=false; if(active) SystemInterface_SDL::DeactivateKeyboard();
    }
    void activate() noexcept {
        active=true;
        if(!cursor.empty()) SystemInterface_SDL::SetMouseCursor(cursor);
        if(keyboard) SystemInterface_SDL::ActivateKeyboard(caret,line_height);
        else SystemInterface_SDL::DeactivateKeyboard();
    }
};
// RmlUi otherwise defers changed text geometry until Render, which leaves
// multiline caret navigation stale in headless execution and before restoration.
template<class T> struct TextControl: T {
    explicit TextControl(const Rml::String& tag):T(tag) {}
    void SetValue(const Rml::String& value) override { T::SetValue(value); this->DirtyLayout(); }
};
struct Environment: Rml::SystemInterface {
    NullRenderer null_renderer;
    Files files;
    Rml::SystemInterface* platform=nullptr;
    double seconds=0;
    std::vector<std::string> errors;
    std::string font_path;
    uint64_t serial=0;
    Rml::ElementInstancerGeneric<TextControl<Rml::ElementFormControlInput>> input_instancer;
    Rml::ElementInstancerGeneric<TextControl<Rml::ElementFormControlTextArea>> textarea_instancer;
    double GetElapsedTime() override { return seconds; }
    bool LogMessage(Rml::Log::Type type,const Rml::String& message) override {
        if(type<=Rml::Log::LT_WARNING && errors.size()<32) errors.push_back(message);
        return true;
    }
    void SetMouseCursor(const Rml::String& name) override { if(platform) platform->SetMouseCursor(name); }
    void SetClipboardText(const Rml::String& text) override { if(platform) platform->SetClipboardText(text); }
    void GetClipboardText(Rml::String& text) override { if(platform) platform->GetClipboardText(text); }
    void ActivateKeyboard(Rml::Vector2f p,float height) override { if(platform) platform->ActivateKeyboard(p,height); }
    void DeactivateKeyboard() override { if(platform) platform->DeactivateKeyboard(); }
    Environment() {
        Rml::SetSystemInterface(this); Rml::SetRenderInterface(&null_renderer); Rml::SetFileInterface(&files);
        require(Rml::Initialise(),"Cannot initialize RmlUi");
        Rml::Factory::RegisterElementInstancer("input",&input_instancer);
        Rml::Factory::RegisterElementInstancer("textarea",&textarea_instancer);
    }
    ~Environment() { platform=nullptr; Rml::Shutdown(); }
    void check() {
        if(errors.empty()) return;
        auto message=errors.front(); errors.clear(); throw std::runtime_error("UI: "+message);
    }
};
std::shared_ptr<Environment> environment() {
    static std::weak_ptr<Environment> shared;
    auto env=shared.lock();
    if(!env) { env=std::make_shared<Environment>(); shared=env; }
    return env;
}
Rml::ElementFormControl* form(Rml::Element* element) {
    auto* control=rmlui_dynamic_cast<Rml::ElementFormControl*>(element);
    require(control,"UI element is not a form control: "+element->GetId()); return control;
}
std::string input_type(Rml::Element* element) { return element->GetAttribute<Rml::String>("type",element->GetTagName()=="input" ? "text" : ""); }
double number(const std::string& text) {
    size_t used=0; const auto value=std::stod(text,&used);
    require(used==text.size() && std::isfinite(value),"UI numeric value is not finite"); return value;
}
std::string plain_text(Rml::Element* element) {
    if(auto* control=rmlui_dynamic_cast<Rml::ElementFormControl*>(element)) return control->GetValue();
    if(auto* text=rmlui_dynamic_cast<Rml::ElementText*>(element)) return text->GetText();
    std::string result;
    for(int i=0;i<element->GetNumChildren();++i) result+=plain_text(element->GetChild(i));
    return result;
}
using Json=nlohmann::json;
void fields(const Json& data,std::initializer_list<const char*> keys) {
    require(data.is_object() && data.size()==keys.size(),"Invalid UI checkpoint fields");
    for(auto key:keys) require(data.contains(key),"Missing UI checkpoint field: "+std::string(key));
}
std::string checkpoint_text(const Json& data) {
    auto text=data.get<std::string>();
    require(text.size()<=65536 && text.find('\0')==std::string::npos,"Invalid UI checkpoint text"); return text;
}
uint64_t counter(const Json& data) {
    require(data.is_number_integer() && (data.is_number_unsigned() || data.get<int64_t>()>=0),"Invalid UI checkpoint counter");
    const auto value=data.get<uint64_t>(); require(value<UINT64_MAX,"Invalid UI checkpoint counter"); return value;
}
double finite(const Json& data,double minimum,double maximum) {
    require(data.is_number(),"Invalid UI checkpoint number"); const auto value=data.get<double>();
    require(std::isfinite(value) && value>=minimum && value<=maximum,"UI checkpoint number is out of range"); return value;
}
Json selection(Rml::Element* element) {
    int start=0,end=0;
    if(auto* input=rmlui_dynamic_cast<Rml::ElementFormControlInput*>(element); input && (input_type(input)=="text" || input_type(input)=="password"))
        input->GetSelection(&start,&end,nullptr);
    else if(auto* area=rmlui_dynamic_cast<Rml::ElementFormControlTextArea*>(element)) area->GetSelection(&start,&end,nullptr);
    else return nullptr;
    return {start,end};
}
}
struct UiSession::Impl: Rml::EventListener {
    std::shared_ptr<Environment> env=environment();
    std::unique_ptr<Platform> platform;
    SDL_Window* window=nullptr;
    Rml::Context* context=nullptr;
    struct Document {
        Rml::ElementDocument* root;
        std::map<std::string,Rml::Element*> elements;
        uint64_t generation;
        nlohmann::json styles=nlohmann::json::array(),texts=nlohmann::json::object();
    };
    std::map<std::string,Document> documents;
    std::vector<UiEvent> events;
    bool overflow=false;
    double seconds=0;
    std::filesystem::path assets;
    uint64_t serial=0;
    int mouse_x=0,mouse_y=0,mouse_modifiers=0;
    unsigned mouse_buttons=0;
    bool mouse_active=false;
    void select() const { env->seconds=seconds; env->platform=platform.get(); env->files.assets=assets; }
    void check() {
        env->check();
        require(!overflow,"UI event queue exceeded 4096 events");
    }
    Document& doc(const std::string& name) {
        const auto it=documents.find(name);
        require(it!=documents.end(),"Unknown UI document: "+name); return it->second;
    }
    Rml::Element* element(const std::string& name,const std::string& id) {
        const auto& elements=doc(name).elements; const auto it=elements.find(id);
        require(it!=elements.end(),"Unknown UI element: "+name+"/"+id); return it->second;
    }
    nlohmann::json address(Rml::Element* element) const {
        if(!element || element==context->GetRootElement()) return nullptr;
        for(const auto& [name,document]:documents) if(element->GetOwnerDocument()==document.root) {
            std::vector<int> path;
            while(element!=document.root) {
                auto* parent=element->GetParentNode(); require(parent,"Detached UI checkpoint element");
                int index=0; while(index<parent->GetNumChildren(true) && parent->GetChild(index)!=element) ++index;
                require(index<parent->GetNumChildren(true),"Missing UI checkpoint element");
                path.push_back(index); element=parent;
            }
            std::reverse(path.begin(),path.end()); return {{"document",name},{"path",path}};
        }
        throw std::runtime_error("Unknown UI checkpoint document");
    }
    Rml::Element* resolve(const nlohmann::json& address) {
        require(address.is_object() && address.size()==2,"Invalid UI element address");
        auto* current=static_cast<Rml::Element*>(doc(address.at("document").get<std::string>()).root);
        const auto& path=address.at("path"); require(path.is_array() && path.size()<=4096,"Invalid UI element path");
        for(const auto& part:path) {
            require(part.is_number_integer() && part>=0 && part<current->GetNumChildren(true),"Invalid UI element index");
            current=current->GetChild(part.get<int>()); require(current,"Missing UI checkpoint element");
        }
        return current;
    }
    std::vector<Rml::Element*> tree(Rml::Element* root) const {
        std::vector<Rml::Element*> result{root};
        for(size_t n=0;n<result.size();++n) {
            require(result.size()<=16384,"UI checkpoint exceeds 16384 elements per document");
            for(int child=0;child<result[n]->GetNumChildren(true);++child) result.push_back(result[n]->GetChild(child));
        }
        return result;
    }
    ~Impl() {
        select();
        if(context) Rml::RemoveContext(context->GetName());
        env->platform=nullptr;
    }
    void ProcessEvent(Rml::Event& event) override {
        auto* target=event.GetTargetElement();
        // Internal range/text children have no public ID; bind events to the
        // nearest named form control, once at the document capture listener.
        while(target && !rmlui_dynamic_cast<Rml::ElementFormControl*>(target)) target=target->GetParentNode();
        if(!target || target->GetId().empty() || form(target)->IsDisabled()) return;
        const auto type=input_type(target); std::string kind;
        if(event.GetType()=="click" && type=="button") kind="click";
        else if(event.GetType()=="change") kind="change";
        else if(event.GetType()=="keydown" && type=="text") {
            const auto key=event.GetParameter<int>("key_identifier",0);
            if(key==Rml::Input::KI_RETURN || key==Rml::Input::KI_NUMPADENTER) kind="submit";
        }
        if(kind.empty()) return;
        for(const auto& [name,document]:documents) if(document.root==target->GetOwnerDocument()) {
            if(events.size()>=4096) { overflow=true; return; }
            events.push_back({name,target->GetId(),kind,form(target)->GetValue(),target->HasAttribute("checked"),document.generation});
            return;
        }
    }
};
UiSession::UiSession(const std::filesystem::path& font,Rml::RenderInterface* renderer,SDL_Window* window,const std::filesystem::path& assets,bool platform_active):impl_(std::make_unique<Impl>()) {
    auto& i=*impl_; i.window=window;
    if(window) i.platform=std::make_unique<Platform>(window,platform_active);
    i.select();
    const auto path=std::filesystem::canonical(font).generic_u8string();
    const std::string filename(path.begin(),path.end());
    require(i.env->font_path.empty() || i.env->font_path==filename,"UI sessions must use the same packaged font");
    if(i.env->font_path.empty()) {
        require(Rml::LoadFontFace(filename,"node-ui",Rml::Style::FontStyle::Normal),"Cannot load UI font: "+filename);
        i.env->font_path=filename;
    }
    i.assets=assets.empty() ? assets : std::filesystem::weakly_canonical(assets); i.select();
    i.context=Rml::CreateContext("node-ui-"+std::to_string(++i.env->serial),{960,640},renderer);
    require(i.context,"Cannot create UI context"); i.check();
}
UiSession::~UiSession()=default;
void UiSession::suspend_platform() noexcept { if(impl_->platform) impl_->platform->active=false; }
void UiSession::activate_platform() noexcept { if(impl_->platform) impl_->platform->activate(); }
bool UiSession::contains(const std::string& name) const { return impl_->documents.contains(name); }
void UiSession::load(const std::string& name,const std::string& markup,const std::string& source) {
    auto& i=*impl_; i.select(); identifier(name);
    require(!contains(name),"UI document already exists: "+name);
    require(i.serial<UINT64_MAX-1,"UI document generation exhausted");
    require(i.documents.size()<128,"At most 128 UI documents are allowed");
    require(!markup.empty() && markup.size()<=1024*1024,"UI template must contain at most 1 MiB of RML");
    // RmlUi's stream URL parser treats ':' as a scheme separator; its path
    // resolver converts this drive placeholder back before opening resources.
    auto url=source;
    if(url.size()>1 && url[1]==':') url[1]='|';
    auto* document=i.context->LoadDocumentFromMemory(markup,url);
    try {
        require(document,"Cannot load UI template"); i.check();
        Impl::Document item{document,{},++i.serial}; std::vector<Rml::Element*> pending{document}; size_t count=0;
        while(!pending.empty()) {
            auto* element=pending.back(); pending.pop_back();
            require(++count<=4096,"UI template exceeds 4096 elements");
            const auto& id=element->GetId();
            if(!id.empty()) { identifier(id); require(item.elements.emplace(id,element).second,"Duplicate UI element ID: "+id); }
            for(int n=0;n<element->GetNumChildren();++n) pending.push_back(element->GetChild(n));
        }
        document->Show(Rml::ModalFlag::None,Rml::FocusFlag::None); i.context->Update(); i.check();
        for(const auto* type:{"click","change","keydown"}) document->AddEventListener(type,&i,true);
        i.documents.emplace(name,std::move(item));
    } catch(...) {
        if(document) { document->Close(); i.context->Update(); }
        i.env->errors.clear(); throw;
    }
}
void UiSession::destroy(const std::string& name) {
    auto& i=*impl_; i.select(); i.doc(name).root->Close(); i.documents.erase(name);
    std::erase_if(i.events,[&](const UiEvent& e){return e.document==name;});
    i.context->Update(); i.check();
}
void UiSession::show(const std::string& name,bool visible) {
    auto& i=*impl_; i.select(); auto& item=i.doc(name); auto* document=item.root;
    if(visible) document->Show(Rml::ModalFlag::None,Rml::FocusFlag::None);
    else { require(i.serial<UINT64_MAX-1,"UI document generation exhausted"); document->Hide(); item.generation=++i.serial; }
    i.check();
}
void UiSession::set_text(const std::string& name,const std::string& id,const std::string& text) {
    require(text.size()<=65536 && text.find('\0')==std::string::npos,"UI text exceeds 64 KiB or contains NUL");
    auto& i=*impl_; i.select(); auto* element=i.element(name,id);
    if(auto* control=rmlui_dynamic_cast<Rml::ElementFormControl*>(element)) {
        require(input_type(element)=="text" || input_type(element)=="button" || element->GetTagName()=="textarea","UI element does not accept text");
        control->SetValue(text);
    } else {
        // Replacing a container would invalidate stable child handles.
        for(int n=0;n<element->GetNumChildren();++n)
            require(rmlui_dynamic_cast<Rml::ElementText*>(element->GetChild(n)),"Set Text requires a plain text element");
        element->SetInnerRML(Rml::StringUtilities::EncodeRml(text));
        i.doc(name).texts[id]=text;
    }
    i.check();
}
std::string UiSession::text(const std::string& name,const std::string& id) const { impl_->select(); return plain_text(impl_->element(name,id)); }
void UiSession::set_value(const std::string& name,const std::string& id,double value) {
    require(std::isfinite(value),"UI numeric value must be finite"); auto& i=*impl_; i.select(); auto* e=i.element(name,id);
    if(auto* progress=rmlui_dynamic_cast<Rml::ElementProgress*>(e)) {
        require(value>=0 && value<=1,"UI progress must be between 0 and 1"); progress->SetValue(float(value));
    } else {
        require(input_type(e)=="range","UI numeric value requires progress or range input");
        const auto lo=e->GetAttribute<double>("min",0),hi=e->GetAttribute<double>("max",100);
        require(value>=lo && value<=hi,"UI slider value is out of range"); form(e)->SetValue(std::to_string(value));
    }
    i.check();
}
double UiSession::value(const std::string& name,const std::string& id) const {
    impl_->select(); auto* e=impl_->element(name,id);
    if(auto* progress=rmlui_dynamic_cast<Rml::ElementProgress*>(e)) return progress->GetValue();
    require(input_type(e)=="range","UI numeric value requires progress or range input"); return number(form(e)->GetValue());
}
void UiSession::set_checked(const std::string& name,const std::string& id,bool checked) {
    auto& i=*impl_; i.select(); auto* e=i.element(name,id); require(input_type(e)=="checkbox","UI element is not a checkbox");
    if(checked) e->SetAttribute("checked",true); else e->RemoveAttribute("checked"); i.check();
}
bool UiSession::checked(const std::string& name,const std::string& id) const {
    impl_->select(); auto* e=impl_->element(name,id); require(input_type(e)=="checkbox","UI element is not a checkbox"); return e->HasAttribute("checked");
}
void UiSession::set_enabled(const std::string& name,const std::string& id,bool enabled) {
    auto& i=*impl_; i.select(); form(i.element(name,id))->SetDisabled(!enabled); i.check();
}
bool UiSession::enabled(const std::string& name,const std::string& id) const { impl_->select(); return !form(impl_->element(name,id))->IsDisabled(); }
void UiSession::set_style(const std::string& name,const std::string& id,const std::string& property,const std::string& value) {
    require(property.size()<=128 && value.size()<=65536 && value.find('\0')==std::string::npos,"UI style exceeds checkpoint limits");
    auto& i=*impl_; i.select(); auto& styles=i.doc(name).styles;
    const bool replacement=std::any_of(styles.begin(),styles.end(),[&](const Json& edit){return edit[0]==id && edit[1]==property;});
    require(replacement || styles.size()<16384,"UI style journal exceeds 16384 declarations");
    const bool accepted=i.element(name,id)->SetProperty(property,value); i.check();
    require(accepted,"Invalid UI style: "+property);
    for(auto it=styles.begin();it!=styles.end();) {
        if((*it)[0]==id && (*it)[1]==property) it=styles.erase(it); else ++it;
    }
    // Keep the last declaration for each property in call order. Shorthands and
    // longhands must retain their relative precedence when replayed.
    styles.push_back({id,property,value});
}
void UiSession::focus(const std::string& name,const std::string& id) {
    auto& i=*impl_; i.select(); require(i.element(name,id)->Focus(),"UI element cannot receive focus"); i.check();
}
void UiSession::update(double seconds,int width,int height,float density) {
    require(std::isfinite(seconds) && seconds>=0 && width>0 && height>0 && std::isfinite(density) && density>0,"Invalid UI time or dimensions");
    auto& i=*impl_; i.seconds=seconds; i.select(); i.context->SetDimensions({width,height});
    i.context->SetDensityIndependentPixelRatio(density); i.context->Update(); i.check();
}
void UiSession::render() { auto& i=*impl_; i.select(); i.context->Render(); i.check(); }
bool UiSession::process(SDL_Event& event) {
    auto& i=*impl_; i.select(); require(i.window,"SDL UI input requires a window");
    if(event.type==SDL_EVENT_KEY_DOWN || event.type==SDL_EVENT_KEY_UP) {
        // SDL may pump an entire key chord before delivering its events.
        // Preserve the modifiers attached to this event, not the current state.
        const auto mods=event.key.mod;
        const int modifiers=((mods&SDL_KMOD_CTRL) ? Rml::Input::KM_CTRL : 0) |
            ((mods&SDL_KMOD_SHIFT) ? Rml::Input::KM_SHIFT : 0) |
            ((mods&SDL_KMOD_ALT) ? Rml::Input::KM_ALT : 0) |
            ((mods&SDL_KMOD_GUI) ? Rml::Input::KM_META : 0) |
            ((mods&SDL_KMOD_NUM) ? Rml::Input::KM_NUMLOCK : 0) |
            ((mods&SDL_KMOD_CAPS) ? Rml::Input::KM_CAPSLOCK : 0);
        const auto key=RmlSDL::ConvertKey(event.key.key);
        bool propagate=event.type==SDL_EVENT_KEY_DOWN ? i.context->ProcessKeyDown(key,modifiers) : i.context->ProcessKeyUp(key,modifiers);
        if(event.type==SDL_EVENT_KEY_DOWN && (event.key.key==SDLK_RETURN || event.key.key==SDLK_KP_ENTER))
            propagate &= i.context->ProcessTextInput('\n');
        i.check(); return propagate;
    }
    // SDL button events can arrive without an intervening motion (embedding,
    // capture, synthetic desktop input). Hit-test the event's actual position.
    if(event.type==SDL_EVENT_MOUSE_BUTTON_DOWN || event.type==SDL_EVENT_MOUSE_BUTTON_UP) {
        const float density=SDL_GetWindowPixelDensity(i.window);
        pointer_move(int(event.button.x*density),int(event.button.y*density),RmlSDL::GetKeyModifierState());
        const int button=event.button.button==SDL_BUTTON_LEFT ? 0 : event.button.button==SDL_BUTTON_RIGHT ? 1 : event.button.button==SDL_BUTTON_MIDDLE ? 2 : -1;
        if(button>=0) return pointer_button(button,event.type==SDL_EVENT_MOUSE_BUTTON_DOWN,RmlSDL::GetKeyModifierState());
    }
    if(event.type==SDL_EVENT_MOUSE_MOTION) {
        const float density=SDL_GetWindowPixelDensity(i.window);
        return pointer_move(int(event.motion.x*density),int(event.motion.y*density),RmlSDL::GetKeyModifierState());
    }
    if(event.type==SDL_EVENT_WINDOW_MOUSE_LEAVE) i.mouse_active=false;
    const bool propagate=RmlSDL::InputEventHandler(i.context,i.window,event); i.check(); return propagate;
}
bool UiSession::pointer_move(int x,int y,int modifiers) {
    auto& i=*impl_; i.select(); i.mouse_x=x; i.mouse_y=y; i.mouse_modifiers=modifiers; i.mouse_active=true;
    const bool p=i.context->ProcessMouseMove(x,y,modifiers); i.check(); return p;
}
bool UiSession::pointer_button(int button,bool down,int modifiers) {
    require(button>=0 && button<3,"UI mouse button must be 0, 1 or 2"); auto& i=*impl_; i.select();
    if(down) i.mouse_buttons|=1u<<button; else i.mouse_buttons&=~(1u<<button);
    i.mouse_modifiers=modifiers;
    const bool p=down ? i.context->ProcessMouseButtonDown(button,modifiers) : i.context->ProcessMouseButtonUp(button,modifiers); i.check(); return p;
}
bool UiSession::text_input(const std::string& text) {
    require(text.size()<=65536 && text.find('\0')==std::string::npos,"UI input exceeds 64 KiB or contains NUL");
    auto& i=*impl_; i.select(); const bool p=i.context->ProcessTextInput(text); i.check(); return p;
}
bool UiSession::key_input(int key,bool down,int modifiers) {
    require(key>=Rml::Input::KI_UNKNOWN && key<=Rml::Input::KI_LAST_CUSTOM_KEY,"Invalid UI key code");
    auto& i=*impl_; i.select(); const auto code=static_cast<Rml::Input::KeyIdentifier>(key);
    const bool p=down ? i.context->ProcessKeyDown(code,modifiers) : i.context->ProcessKeyUp(code,modifiers); i.check(); return p;
}
std::vector<UiEvent> UiSession::take_events() { impl_->check(); std::vector<UiEvent> result; result.swap(impl_->events); return result; }
bool UiSession::alive(const UiEvent& event) const {
    const auto it=impl_->documents.find(event.document);
    if(it==impl_->documents.end() || it->second.generation!=event.generation || !it->second.root->IsVisible()) return false;
    const auto element=it->second.elements.find(event.element);
    return element!=it->second.elements.end() && element->second->IsVisible() && !form(element->second)->IsDisabled();
}
void UiSession::clear_input() {
    auto& i=*impl_; i.select(); i.context->ProcessMouseLeave();
    for(int button=0;button<3;++button) i.context->ProcessMouseButtonUp(button,0);
    if(auto* focus=i.context->GetFocusElement()) focus->Blur();
    i.events.clear(); i.overflow=false; i.check();
    i.mouse_buttons=0; i.mouse_active=false; i.mouse_modifiers=0;
}
nlohmann::json UiSession::snapshot() const {
    impl_->select(); auto result=nlohmann::json::object();
    for(const auto& [name,doc]:impl_->documents) {
        auto elements=nlohmann::json::object();
        for(const auto& [id,e]:doc.elements) {
            nlohmann::json state={{"text",plain_text(e)},{"visible",e->IsVisible()}};
            if(auto* control=rmlui_dynamic_cast<Rml::ElementFormControl*>(e)) state["enabled"]=!control->IsDisabled();
            if(input_type(e)=="checkbox") state["checked"]=e->HasAttribute("checked");
            if(input_type(e)=="range" || rmlui_dynamic_cast<Rml::ElementProgress*>(e)) state["value"]=value(name,id);
            elements[id]=std::move(state);
        }
        result[name]={{"visible",doc.root->IsVisible()},{"elements",elements}};
    }
    return result;
}
Json UiSession::checkpoint() const {
    auto& i=*impl_; i.select(); i.check();
    require(!i.mouse_buttons,"UI checkpoint requires released pointer buttons");
    Json documents=Json::array(),order=Json::array(),events=Json::array();
    for(const auto& [name,doc]:i.documents) {
        Json controls=Json::array(),progress=Json::array(),scroll=Json::array();
        for(auto* e:i.tree(doc.root)) {
            if(auto* control=rmlui_dynamic_cast<Rml::ElementFormControl*>(e)) {
                Json index=nullptr;
                if(auto* select=rmlui_dynamic_cast<Rml::ElementFormControlSelect*>(e)) {
                    require(!select->IsSelectBoxVisible(),"UI checkpoint requires closed select menus"); index=select->GetSelection();
                }
                controls.push_back({{"at",i.address(e)},{"value",checkpoint_text(control->GetValue())},
                    {"disabled",control->IsDisabled()},{"checked",e->HasAttribute("checked")},{"index",index},{"selection",selection(e)}});
            }
            if(auto* p=rmlui_dynamic_cast<Rml::ElementProgress*>(e)) progress.push_back({{"at",i.address(e)},{"value",p->GetValue()}});
            if(e->GetScrollLeft()!=0 || e->GetScrollTop()!=0) scroll.push_back({{"at",i.address(e)},{"x",e->GetScrollLeft()},{"y",e->GetScrollTop()}});
        }
        documents.push_back({{"name",name},{"generation",doc.generation},{"visible",doc.root->IsVisible()},
            {"texts",doc.texts},{"styles",doc.styles},{"controls",controls},{"progress",progress},{"scroll",scroll},
            {"focus_leaf",i.address(doc.root->GetFocusLeafNode())}});
    }
    for(int n=0;n<i.context->GetNumDocuments();++n) order.push_back(i.address(i.context->GetDocument(n)).at("document"));
    Json focus=nullptr,history=Json::array();
    for(auto* e:i.context->GetDocumentFocusHistory()) if(e!=i.context->GetRootElement()) history.push_back(i.address(e).at("document"));
    if(auto* e=i.context->GetFocusElement(); e && e!=i.context->GetRootElement()) focus={{"at",i.address(e)},{"selection",selection(e)}};
    for(const auto& event:i.events) events.push_back({{"document",event.document},{"element",event.element},{"type",event.type},
        {"value",checkpoint_text(event.value)},{"checked",event.checked},{"generation",event.generation}});
    const auto size=i.context->GetDimensions();
    Json result={{"version",1},{"serial",i.serial},{"seconds",i.seconds},{"dimensions",{size.x,size.y}},
        {"density",i.context->GetDensityIndependentPixelRatio()},{"documents",documents},{"order",order},{"focus",focus},{"focus_history",history},
        {"pointer",{{"x",i.mouse_x},{"y",i.mouse_y},{"modifiers",i.mouse_modifiers},{"active",i.mouse_active}}},{"events",events}};
    require(result.dump().size()<=32*1024*1024,"UI checkpoint exceeds 32 MiB"); return result;
}
void UiSession::restore_checkpoint(const Json& data) {
    fields(data,{"version","serial","seconds","dimensions","density","documents","order","focus","focus_history","pointer","events"});
    require(data.at("version").is_number_integer() && data.at("version")==1 && data.dump().size()<=32*1024*1024,"Invalid UI checkpoint version/size");
    auto& i=*impl_; i.select();
    require(!i.mouse_buttons,"UI restore requires released pointer buttons");
    const auto serial=counter(data.at("serial"));
    const auto& dimensions=data.at("dimensions");
    require(dimensions.is_array() && dimensions.size()==2 && dimensions[0].is_number_integer() && dimensions[1].is_number_integer(),"Invalid UI checkpoint dimensions");
    const int width=int(finite(dimensions[0],1,1000000)),height=int(finite(dimensions[1],1,1000000));
    const auto seconds=finite(data.at("seconds"),0,1e15); const float density=float(finite(data.at("density"),.0001,10000));
    const auto& documents=data.at("documents");
    require(documents.is_array() && documents.size()==i.documents.size(),"UI checkpoint documents do not match instances");
    std::set<std::string> names; std::set<uint64_t> generations;
    update(seconds,width,height,density);
    for(const auto& state:documents) {
        fields(state,{"name","generation","visible","texts","styles","controls","progress","scroll","focus_leaf"});
        const auto name=state.at("name").get<std::string>(); auto& doc=i.doc(name);
        require(names.insert(name).second,"Duplicate UI checkpoint document");
        const auto generation=counter(state.at("generation"));
        require(generation>0 && generation<=serial && generations.insert(generation).second,"Invalid UI document generation");
        const auto& texts=state.at("texts"); require(texts.is_object() && texts.size()<=4096,"Invalid UI checkpoint text edits");
        for(const auto& [id,text]:texts.items()) {
            require(!rmlui_dynamic_cast<Rml::ElementFormControl*>(i.element(name,id)),"UI text journal contains a form control");
            set_text(name,id,checkpoint_text(text));
        }
        const auto& styles=state.at("styles"); require(styles.is_array() && styles.size()<=16384,"Invalid UI checkpoint styles");
        std::set<std::pair<std::string,std::string>> properties;
        for(const auto& edit:styles) {
            require(edit.is_array() && edit.size()==3,"Invalid UI checkpoint style declaration");
            const auto id=edit[0].get<std::string>(),property=edit[1].get<std::string>();
            require(properties.emplace(id,property).second,"Duplicate UI style declaration"); set_style(name,id,property,checkpoint_text(edit[2]));
        }
        const auto& controls=state.at("controls"); require(controls.is_array() && controls.size()<=16384,"Invalid UI checkpoint controls");
        std::set<Rml::Element*> seen;
        for(const auto& entry:controls) {
            fields(entry,{"at","value","disabled","checked","index","selection"}); auto* e=i.resolve(entry.at("at"));
            require(e->GetOwnerDocument()==doc.root && seen.insert(e).second,"Wrong or duplicate UI checkpoint control");
            auto* control=form(e); control->SetValue(checkpoint_text(entry.at("value"))); control->SetDisabled(entry.at("disabled").get<bool>());
            if(entry.at("checked").get<bool>()) e->SetAttribute("checked",true); else e->RemoveAttribute("checked");
            if(auto* select=rmlui_dynamic_cast<Rml::ElementFormControlSelect*>(e)) {
                require(entry.at("index").is_number_integer(),"Invalid UI select index");
                select->SetSelection(int(finite(entry.at("index"),-1,select->GetNumOptions()-1)));
            } else require(entry.at("index").is_null(),"Unexpected UI select index");
        }
        const auto& progress=state.at("progress"); require(progress.is_array() && progress.size()<=16384,"Invalid UI checkpoint progress controls");
        seen.clear();
        for(const auto& entry:progress) {
            fields(entry,{"at","value"}); auto* e=i.resolve(entry.at("at"));
            auto* p=rmlui_dynamic_cast<Rml::ElementProgress*>(e);
            require(p && e->GetOwnerDocument()==doc.root && seen.insert(e).second,"Wrong or duplicate UI progress control");
            p->SetValue(float(finite(entry.at("value"),0,1)));
        }
        show(name,state.at("visible").get<bool>()); doc.generation=generation;
    }
    i.serial=serial; update(seconds,width,height,density);
    auto restore_selection=[&](Rml::Element* e,const Json& range) {
        if(range.is_null()) { require(selection(e).is_null(),"Missing UI text selection"); return; }
        require(!selection(e).is_null() && range.is_array() && range.size()==2 && range[0].is_number_integer() && range[1].is_number_integer(),"Invalid UI selection");
        const int start=int(finite(range[0],0,65536)),end=int(finite(range[1],start,65536));
        require(e->Focus(),"Cannot restore UI control caret");
        if(auto* input=rmlui_dynamic_cast<Rml::ElementFormControlInput*>(e)) input->SetSelectionRange(start,end);
        else rmlui_dynamic_cast<Rml::ElementFormControlTextArea*>(e)->SetSelectionRange(start,end);
    };
    for(const auto& state:documents) {
        for(const auto& control:state.at("controls")) restore_selection(i.resolve(control.at("at")),control.at("selection"));
        auto* leaf=i.resolve(state.at("focus_leaf"));
        require(leaf->GetOwnerDocument()==i.doc(state.at("name")).root,"Wrong UI document focus leaf");
        require(leaf->Focus() || leaf==leaf->GetOwnerDocument(),"Cannot restore UI document focus leaf");
    }
    const auto& history=data.at("focus_history"); require(history.is_array() && history.size()<=documents.size(),"Invalid UI focus history");
    std::set<std::string> focused;
    Rml::Vector<Rml::Element*> focus_history{i.context->GetRootElement()};
    for(const auto& name:history) {
        const auto text=name.get<std::string>(); require(focused.insert(text).second,"Duplicate UI focus history");
        focus_history.push_back(i.doc(text).root);
    }
    const auto& focus=data.at("focus");
    if(!focus.is_null()) {
        fields(focus,{"at","selection"}); auto* e=i.resolve(focus.at("at")); require(e->Focus(),"Cannot restore UI focus");
        const auto& range=focus.at("selection");
        restore_selection(e,range);
    } else require(i.context->ClearCheckpointFocus(),"Cannot restore an unfocused UI context");
    i.context->SetDocumentFocusHistory(focus_history);
    const auto& order=data.at("order"); require(order.is_array() && order.size()==names.size(),"Invalid UI document order");
    for(const auto& name:order) {
        const auto text=name.get<std::string>(); require(names.erase(text)==1,"Unknown or duplicate ordered UI document");
        i.context->PullDocumentToFront(i.doc(text).root);
    }
    update(seconds,width,height,density);
    for(const auto& state:documents) {
        const auto& scroll=state.at("scroll"); require(scroll.is_array() && scroll.size()<=16384,"Invalid UI checkpoint scroll positions");
        std::set<Rml::Element*> seen;
        for(const auto& entry:scroll) {
            fields(entry,{"at","x","y"}); auto* e=i.resolve(entry.at("at"));
            require(e->GetOwnerDocument()==i.doc(state.at("name")).root && seen.insert(e).second,"Wrong or duplicate UI scroll target");
            e->SetScrollLeft(float(finite(entry.at("x"),0,1e9))); e->SetScrollTop(float(finite(entry.at("y"),0,1e9)));
        }
    }
    const auto& pointer=data.at("pointer"); fields(pointer,{"x","y","modifiers","active"});
    require(pointer.at("x").is_number_integer() && pointer.at("y").is_number_integer() && pointer.at("modifiers").is_number_integer(),"Invalid UI pointer coordinates");
    i.mouse_x=int(finite(pointer.at("x"),INT_MIN,INT_MAX)); i.mouse_y=int(finite(pointer.at("y"),INT_MIN,INT_MAX));
    i.mouse_modifiers=int(finite(pointer.at("modifiers"),0,127)); i.mouse_active=pointer.at("active").get<bool>();
    if(i.mouse_active) pointer_move(i.mouse_x,i.mouse_y,i.mouse_modifiers); else i.context->ProcessMouseLeave();
    update(seconds,width,height,density);
    const auto& events=data.at("events"); require(events.is_array() && events.size()<=4096,"Invalid UI checkpoint event queue");
    i.events.clear(); i.overflow=false;
    for(const auto& entry:events) {
        fields(entry,{"document","element","type","value","checked","generation"});
        UiEvent event{entry.at("document").get<std::string>(),entry.at("element").get<std::string>(),entry.at("type").get<std::string>(),
            checkpoint_text(entry.at("value")),entry.at("checked").get<bool>(),counter(entry.at("generation"))};
        auto* e=i.element(event.document,event.element); form(e);
        require(event.generation>0 && event.generation<=i.doc(event.document).generation,"Invalid UI event generation");
        require(event.type=="change" || (event.type=="click" && input_type(e)=="button") || (event.type=="submit" && input_type(e)=="text"),"Invalid UI checkpoint event kind");
        i.events.push_back(std::move(event));
    }
    i.check();
    const auto restored=checkpoint();
    require(restored==data,"UI checkpoint state cannot be restored exactly");
}
}
