import React,{createContext,useContext,useState} from 'react';
const ChatContext=createContext(null);
export function ChatProvider({children}){const [active,setActive]=useState(null);return <ChatContext.Provider value={{active,setActive}}>{children}</ChatContext.Provider>}
export const useChat=()=>useContext(ChatContext);
