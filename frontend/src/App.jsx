import React, {useEffect, useMemo, useState} from 'react';
import { Welcome, Login, SignIn, Dashboard } from './pages';
import { AuthProvider, useAuth } from './context/AuthContext';

function Router(){
 const {user}=useAuth(); const [page,setPage]=useState(user?'dashboard':'welcome');
 useEffect(()=>{ if(user && page==='welcome') setPage('dashboard'); if(!user && page==='dashboard') setPage('welcome'); },[user]);
 if(page==='welcome') return <Welcome onLogin={()=>setPage('login')} onSignIn={()=>setPage('signin')}/>;
 if(page==='login') return <Login onBack={()=>setPage('welcome')} onSuccess={()=>setPage('dashboard')}/>;
 if(page==='signin') return <SignIn onBack={()=>setPage('welcome')} onSuccess={()=>setPage('dashboard')} />;
 return <Dashboard/>;
}
export default function App(){return <AuthProvider><Router/></AuthProvider>}
