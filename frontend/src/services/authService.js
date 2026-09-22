
import {login as apiLogin,signup as apiSignup} from './api';
export async function createAccount(d){return apiSignup({employee_id:d.employeeId,username:d.username,password:d.password,role:d.role})}
export async function authenticate(identifier,password,role){return apiLogin({identifier,password,role})}
