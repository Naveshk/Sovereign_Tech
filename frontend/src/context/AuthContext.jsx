import React,{createContext,useContext,useMemo,useState} from 'react';
const AuthContext=createContext(null);
const KEY='sovereign_auth';
export function AuthProvider({children}){
 const [user,setUser]=useState(()=>{try{return JSON.parse(localStorage.getItem(KEY))}catch{return null}});
 const login=(u)=>{setUser(u);localStorage.setItem(KEY,JSON.stringify(u));};
 const logout=()=>{setUser(null);localStorage.removeItem(KEY)};
 const value=useMemo(()=>({user,login,logout}),[user]);
 return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export const useAuth=()=>useContext(AuthContext);
