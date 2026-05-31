const {createApp}=Vue;

createApp({

data(){

return{

mode:"login",

loginForm:{
role:"",
email:"",
password:""
},

registerForm:{
role:"",
email:"",
name:"",
company_name:"",
age:"",
gender:"",
phone:"",
password:""
}

}

},


methods:{


async login(){

if(!this.loginForm.role){

alert("Please select role")
return

}

const response = await fetch("/api/login",{

method:"POST",

headers:{"Content-Type":"application/json"},

body:JSON.stringify(this.loginForm)

})

const result = await response.json()

if(response.ok){

window.location.href = result.redirect

}else{

alert(result.message || "Login failed")

}

},



async register() {
    if (!this.registerForm.role) {
        alert("Select register role");
        return;
    }

    try {
        const response = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(this.registerForm)
        });

        // We check if the response is actually JSON before parsing
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            const result = await response.json();
            
            if (response.ok) {
                alert("Success: " + (result.message || "Registration completed"));
                this.mode = "login";
            } else {
                alert("Wait: " + (result.message || "Email already exists or invalid data"));
            }
        } else {
            // If the server crashed and sent an HTML error page instead of JSON
            const errorText = await response.text();
            console.error("Server Error HTML:", errorText);
            alert("Server Error: The backend crashed. Check your Python terminal!");
        }

    } catch (error) {
        // This catches network errors or JS crashes
        console.error("Connection Error:", error);
        alert("Could not connect to the server. Is your Flask app running?");
    }
}

}

}).mount("#app")