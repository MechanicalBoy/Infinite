#pragma once

// The OSC control API (v0.6 2.31): a UDP OSC server that lets an external
// script or controller set, query and listen to any node param, and create,
// delete and connect nodes. The address map lives in app/graph/OscApi.cpp;
// this file is only the socket, the queue and the reply path.
//
// Bound to 127.0.0.1 only, the same policy as RemoteControl and OSC Receive:
// it can delete nodes, so it is not offered to the network.
//
// Threading: one receive thread queues decoded messages; DrainPending() runs
// the handler for each on the main thread (once per frame, next to
// RemoteControl::DrainPending), so the handler may touch the graph. Send()
// is main-thread only.

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "OscMessage.h"

namespace OscControl
{
   // Who sent a message; replies go back to it.
   struct Peer
   {
      uint32_t ip = 0;   // network byte order
      uint16_t port = 0; // network byte order
      bool operator==(const Peer& o) const { return ip == o.ip && port == o.port; }
   };

   struct Request
   {
      std::string address;
      std::vector<OscMessage::Arg> args;
      Peer from;
   };

   // Binds 127.0.0.1:port and starts the receive thread. False if the port is
   // taken (another instance); true and a no-op if already running.
   bool Start(int port);
   void Stop();
   int BoundPort(); // -1 when stopped

   using Handler = std::function<void(const Request&)>;
   void DrainPending(const Handler& handler);

   void Send(const Peer& to, const std::string& address, const std::vector<OscMessage::Arg>& args);

   // A loopback client of the server, for the selftest (sockets stay in this
   // file, so no other translation unit has to include winsock).
   class Client
   {
   public:
      bool Open(int serverPort);
      ~Client();
      void Send(const std::string& address, const std::vector<OscMessage::Arg>& args);
      // One reply if one is waiting (waits at most a few ms).
      bool Receive(std::string& outAddress, std::vector<OscMessage::Arg>& outArgs);

   private:
      int mFd = -1;
      int mServerPort = 0;
   };
}
