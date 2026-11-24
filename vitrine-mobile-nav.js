/* Navegação acessível da Vitrine Certeira */
(function(){
  function initMobileNavigation(){
    document.querySelectorAll('header').forEach(function(header,index){
      var nav=header.querySelector('nav.vc-nav,nav.navlinks');
      if(!nav||nav.dataset.vcMobileReady==='true')return;
      nav.dataset.vcMobileReady='true';
      if(!nav.id)nav.id='vc-navigation-'+(index+1);

      var toggle=document.createElement('button');
      toggle.type='button';
      toggle.className='vc-menu-toggle';
      toggle.setAttribute('aria-controls',nav.id);
      toggle.setAttribute('aria-expanded','false');
      toggle.setAttribute('aria-label','Abrir menu de navegação');
      toggle.innerHTML='<span></span><span></span><span></span><span class="vc-sr-only">Menu</span>';
      nav.parentNode.insertBefore(toggle,nav);

      function closeMenu(){
        header.classList.remove('vc-menu-open');
        toggle.setAttribute('aria-expanded','false');
        toggle.setAttribute('aria-label','Abrir menu de navegação');
      }
      toggle.addEventListener('click',function(){
        var isOpen=toggle.getAttribute('aria-expanded')==='true';
        if(isOpen){closeMenu();return;}
        header.classList.add('vc-menu-open');
        toggle.setAttribute('aria-expanded','true');
        toggle.setAttribute('aria-label','Fechar menu de navegação');
      });
      nav.addEventListener('click',function(event){
        if(event.target.closest('a'))closeMenu();
      });
      document.addEventListener('keydown',function(event){
        if(event.key==='Escape')closeMenu();
      });
      document.addEventListener('click',function(event){
        if(!header.contains(event.target))closeMenu();
      });
    });
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',initMobileNavigation,{once:true});
  }else{
    initMobileNavigation();
  }
})();
