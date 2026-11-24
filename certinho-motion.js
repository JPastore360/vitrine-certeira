/* Certinho micro-interactions and animated mood states */
(()=>{const panel=document.getElementById('aiPanel'),launch=document.getElementById('aiLaunch'),input=document.getElementById('aiInput');if(!panel||!launch)return;
const setMood=m=>{panel.dataset.mood=m;launch.dataset.mood=m};
launch.addEventListener('click',()=>{setMood('hello');setTimeout(()=>setMood('idle'),1800)});
if(input){input.addEventListener('focus',()=>setMood('listening'));input.addEventListener('input',()=>setMood(input.value?'thinking':'listening'))}
const messages=document.getElementById('aiMessages');if(messages){const observer=new MutationObserver(()=>{setMood('discover');setTimeout(()=>setMood('idle'),2400)});observer.observe(messages,{childList:true});}
document.getElementById('aiClose')?.addEventListener('click',()=>setMood('idle'));
})();
