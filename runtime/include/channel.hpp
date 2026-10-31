#pragma once
#include "runtime.hpp"
#include <cstdint>
#include <filesystem>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#endif
namespace rt {
// QLocalSocket wire contract: uint32 little endian byte count, UTF-8 JSON.
// The editor owns a unique local server for each runtime process.
class Channel {
    std::vector<char> buffer;
#ifdef _WIN32
    HANDLE handle=INVALID_HANDLE_VALUE;
#else
    int handle=-1;
#endif
public:
    ~Channel() {
#ifdef _WIN32
        if(handle!=INVALID_HANDLE_VALUE) CloseHandle(handle);
#else
        if(handle>=0) close(handle);
#endif
    }
    void connect(const std::string& name) {
#ifdef _WIN32
        auto path=name.starts_with("\\\\") ? name : "\\\\.\\pipe\\"+name;
        auto wide=std::filesystem::u8path(path).wstring();
        handle=CreateFileW(wide.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_EXISTING,0,nullptr);
        if(handle==INVALID_HANDLE_VALUE) throw std::runtime_error("Cannot connect editor pipe");
#else
        handle=socket(AF_UNIX,SOCK_STREAM,0);
        sockaddr_un address{}; address.sun_family=AF_UNIX;
        if(name.size()>=sizeof(address.sun_path)) throw std::runtime_error("Local socket path too long");
        std::memcpy(address.sun_path,name.c_str(),name.size()+1);
        if(::connect(handle,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0)
            throw std::runtime_error("Cannot connect editor socket");
#endif
    }
    void send(Json message) {
        message["protocol_version"]=1;
        std::string text=message.dump();
        if(text.size()>16*1024*1024) throw std::runtime_error("IPC message too large");
        uint32_t n=static_cast<uint32_t>(text.size());
        std::string bytes(4,'\0');
        for(int i=0;i<4;++i) bytes[i]=static_cast<char>((n>>(i*8))&255);
        bytes+=text;
        size_t offset=0;
        while(offset<bytes.size()) {
#ifdef _WIN32
            DWORD written=0;
            if(!WriteFile(handle,bytes.data()+offset,static_cast<DWORD>(bytes.size()-offset),&written,nullptr) || !written)
                throw std::runtime_error("Editor pipe disconnected");
#else
            auto written=::send(handle,bytes.data()+offset,bytes.size()-offset,MSG_NOSIGNAL);
            if(written<=0) throw std::runtime_error("Editor socket disconnected");
#endif
            offset+=written;
        }
    }
    std::vector<Json> receive() {
        char bytes[65536];
#ifdef _WIN32
        DWORD available=0, received=0;
        if(!PeekNamedPipe(handle,nullptr,0,nullptr,&available,nullptr))
            throw std::runtime_error("Editor pipe disconnected");
        if(available) {
            if(!ReadFile(handle,bytes,std::min<DWORD>(available,sizeof(bytes)),&received,nullptr))
                throw std::runtime_error("Editor pipe read failed");
            buffer.insert(buffer.end(),bytes,bytes+received);
        }
#else
        auto received=recv(handle,bytes,sizeof(bytes),MSG_DONTWAIT);
        if(received==0) throw std::runtime_error("Editor socket disconnected");
        if(received>0) buffer.insert(buffer.end(),bytes,bytes+received);
        else if(errno!=EAGAIN && errno!=EWOULDBLOCK) throw std::runtime_error("Editor socket read failed");
#endif
        std::vector<Json> messages;
        while(buffer.size()>=4) {
            uint32_t length=0;
            for(int i=0;i<4;++i) length |= uint32_t(uint8_t(buffer[i]))<<(i*8);
            if(length>16*1024*1024) throw std::runtime_error("IPC frame exceeds 16 MiB");
            if(buffer.size()<length+4) break;
            auto message=Json::parse(buffer.begin()+4,buffer.begin()+4+length);
            if(message.value("protocol_version",0)!=1) throw std::runtime_error("IPC protocol version mismatch");
            messages.push_back(std::move(message));
            buffer.erase(buffer.begin(),buffer.begin()+4+length);
        }
        return messages;
    }
};
}
