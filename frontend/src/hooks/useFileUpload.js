import {useState} from 'react';export default function useFileUpload(){const[file,setFile]=useState(null);return{file,setFile,clear:()=>setFile(null)}}
