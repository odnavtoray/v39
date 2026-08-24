
async function shareUrl(path,title){
  const url=new URL(path,location.origin).href;
  const ru=document.documentElement.lang==="ru";
  const data={
    title:title||"1/2 — Одна Друга",
    text:ru?"Посмотрите это объявление на 1/2 — Одна Друга":"Подивіться це оголошення на 1/2 — Одна Друга",
    url
  };

  // On a real HTTPS domain iOS/Android opens the native share sheet.
  if(navigator.share){
    try{
      await navigator.share(data);
      return;
    }catch(e){
      if(e && e.name==="AbortError")return;
    }
  }

  // Local Wi-Fi HTTP is not a secure context on phones, so Web Share may be unavailable.
  // Give a useful messenger chooser instead of an inert prompt.
  document.getElementById("localShareSheet")?.remove();
  const sheet=document.createElement("div");
  sheet.id="localShareSheet";
  sheet.className="local-share-sheet";
  const encodedUrl=encodeURIComponent(url);
  const encodedText=encodeURIComponent(`${data.text}
${url}`);
  sheet.innerHTML=`
    <div class="local-share-backdrop" data-close-share></div>
    <div class="local-share-panel" role="dialog" aria-modal="true">
      <div class="local-share-handle"></div>
      <h3>${ru?"Поделиться объявлением":"Поділитися оголошенням"}</h3>
      <div class="local-share-grid">
        <a href="https://t.me/share/url?url=${encodedUrl}&text=${encodeURIComponent(data.text)}" target="_blank" rel="noopener">Telegram</a>
        <a href="https://wa.me/?text=${encodedText}" target="_blank" rel="noopener">WhatsApp</a>
        <a href="viber://forward?text=${encodedText}">Viber</a>
        <a href="sms:?&body=${encodedText}">${ru?"Сообщения":"Повідомлення"}</a>
      </div>
      <button type="button" class="local-share-copy">${ru?"Копировать ссылку":"Копіювати посилання"}</button>
      <button type="button" class="local-share-cancel" data-close-share>${ru?"Отмена":"Скасувати"}</button>
    </div>`;
  document.body.appendChild(sheet);
  sheet.querySelectorAll("[data-close-share]").forEach(x=>x.addEventListener("click",()=>sheet.remove()));
  sheet.querySelector(".local-share-copy")?.addEventListener("click",async()=>{
    try{
      await navigator.clipboard.writeText(url);
      sheet.querySelector(".local-share-copy").textContent=ru?"Ссылка скопирована":"Посилання скопійовано";
    }catch(e){
      const input=document.createElement("input");
      input.value=url;document.body.appendChild(input);input.select();document.execCommand("copy");input.remove();
      sheet.querySelector(".local-share-copy").textContent=ru?"Ссылка скопирована":"Посилання скопійовано";
    }
  });
}
function shareListing(){shareUrl(location.pathname+location.search,document.querySelector(".detail-top h1")?.innerText||"Оголошення")}

const catalog=document.getElementById("catalog");
const listBtn=document.getElementById("listBtn"), gridBtn=document.getElementById("gridBtn");
if(catalog&&listBtn&&gridBtn){
  listBtn.onclick=()=>{catalog.classList.add("listmode");catalog.classList.remove("gridmode");listBtn.classList.add("active");gridBtn.classList.remove("active")}
  gridBtn.onclick=()=>{catalog.classList.remove("listmode");catalog.classList.add("gridmode");gridBtn.classList.add("active");listBtn.classList.remove("active")}
}

// Photo editor: first photo is always main. Drag works with mouse and touch.
const input=document.getElementById("photoInput");
const stage=document.getElementById("stageImage");
const emptyStage=document.getElementById("emptyStage");
const strip=document.getElementById("photoStrip");
const form=document.getElementById("listingForm");
let photoItems=[];
let dragIndex=null;
let pointerDragIndex=null;
let previewItem=null; // what is shown large; independent from main/order

function fileToData(file){
  return new Promise((resolve,reject)=>{
    const r=new FileReader();
    r.onload=()=>resolve(r.result);
    r.onerror=reject;
    r.readAsDataURL(file);
  });
}
async function loadFiles(files){
  const arr=[...files];
  const remaining=Math.max(0,5-photoItems.length);
  const add=arr.slice(0,remaining);
  for(const f of add){
    const item={file:f,url:await fileToData(f),rot:0};
    photoItems.push(item);
    if(!previewItem)previewItem=item;
  }
  if(arr.length>remaining) alert(document.documentElement.lang==="ru" ? "Можно добавить максимум 5 фотографий." : "Можна додати максимум 5 фотографій.");
  if(input) input.value="";
  renderPhotoEditor();
  updatePublishState();
}
function movePhoto(from,to){
  if(from===to || from==null || to==null || from<0 || to<0 || from>=photoItems.length || to>=photoItems.length)return;
  const item=photoItems.splice(from,1)[0];
  photoItems.splice(to,0,item);
  renderPhotoEditor();
}
function previewPhoto(item){
  if(!item)return;
  previewItem=item;
  renderPhotoEditor();
}
function renderPhotoEditor(){
  if(!stage||!strip)return;
  strip.innerHTML="";
  if(!photoItems.length){
    previewItem=null;
    stage.hidden=true;
    emptyStage.hidden=false;
    const tools=document.getElementById("mainPhotoTools");
    if(tools)tools.hidden=true;
    return;
  }

  if(!previewItem || !photoItems.includes(previewItem)) previewItem=photoItems[0];

  emptyStage.hidden=true;
  stage.hidden=false;
  stage.src=previewItem.url;
  stage.style.transform=`rotate(${previewItem.rot}deg)`;
  stage.dataset.previewIndex=String(photoItems.indexOf(previewItem));

  photoItems.forEach((p,i)=>{
    const el=document.createElement("div");
    const isPreview=p===previewItem;
    el.className="thumb-edit"+(i===0?" selected":"")+(isPreview?" is-preview":"");
    el.dataset.index=i;
    el.draggable=window.matchMedia?.("(pointer:fine)")?.matches ?? true;
    el.innerHTML=`
      <span class="photo-order-badge">${i+1}</span>
      ${i===0?`<span class="photo-main-badge">${document.documentElement.lang==="ru"?"Главное фото":"Головне фото"}</span>`:""}
      <img src="${p.url}" draggable="false" style="transform:rotate(${p.rot}deg)">
      <div class="thumb-tools">
        <button type="button" data-act="left" aria-label="rotate left">↺</button>
        <button type="button" data-act="right" aria-label="rotate right">↻</button>
        <button type="button" data-act="del" aria-label="delete">×</button>
      </div>`;

    // Tap/click only previews this photo. It NEVER changes order/main.
    el.addEventListener("click",(e)=>{
      if(e.target.closest("button"))return;
      previewPhoto(p);
    });

    // Desktop drag & drop changes order. First position is main.
    el.addEventListener("dragstart",(e)=>{
      dragIndex=Number(el.dataset.index);
      el.classList.add("dragging");
      e.dataTransfer.effectAllowed="move";
    });
    el.addEventListener("dragend",()=>{
      dragIndex=null;
      document.querySelectorAll(".thumb-edit").forEach(x=>x.classList.remove("dragging","drag-over"));
    });
    el.addEventListener("dragover",(e)=>{
      e.preventDefault();
      el.classList.add("drag-over");
    });
    el.addEventListener("dragleave",()=>el.classList.remove("drag-over"));
    el.addEventListener("drop",(e)=>{
      e.preventDefault();
      const to=Number(el.dataset.index);
      el.classList.remove("drag-over");
      if(dragIndex!==null)movePhoto(dragIndex,to);
    });

    // Touch / pointer reorder.
    el.addEventListener("pointerdown",(e)=>{
      if(e.target.closest("button"))return;
      if(e.pointerType==="mouse")return;
      e.preventDefault();
      pointerDragIndex=Number(el.dataset.index);
      el.setPointerCapture?.(e.pointerId);
      el.classList.add("dragging");
    },{passive:false});
    el.addEventListener("pointermove",(e)=>{
      if(pointerDragIndex===null)return;
      e.preventDefault();
      const target=document.elementFromPoint(e.clientX,e.clientY)?.closest?.(".thumb-edit");
      if(target){
        document.querySelectorAll(".thumb-edit").forEach(x=>x.classList.remove("drag-over"));
        target.classList.add("drag-over");
      }
    },{passive:false});
    const finishPointer=(e)=>{
      if(pointerDragIndex===null)return;
      const target=document.elementFromPoint(e.clientX,e.clientY)?.closest?.(".thumb-edit");
      const from=pointerDragIndex;
      pointerDragIndex=null;
      document.querySelectorAll(".thumb-edit").forEach(x=>x.classList.remove("dragging","drag-over"));
      if(target)movePhoto(from,Number(target.dataset.index));
    };
    el.addEventListener("pointerup",finishPointer);
    el.addEventListener("pointercancel",()=>{
      pointerDragIndex=null;
      document.querySelectorAll(".thumb-edit").forEach(x=>x.classList.remove("dragging","drag-over"));
    });

    el.querySelector('[data-act="left"]').onclick=(e)=>{
      e.stopPropagation();
      p.rot=(p.rot-90)%360;
      previewItem=p;
      renderPhotoEditor();
    };
    el.querySelector('[data-act="right"]').onclick=(e)=>{
      e.stopPropagation();
      p.rot=(p.rot+90)%360;
      previewItem=p;
      renderPhotoEditor();
    };
    el.querySelector('[data-act="del"]').onclick=(e)=>{
      e.stopPropagation();
      const wasPreview=previewItem===p;
      photoItems.splice(i,1);
      if(wasPreview)previewItem=photoItems[Math.min(i,photoItems.length-1)] || photoItems[0] || null;
      renderPhotoEditor();
      updatePublishState();
    };
    strip.appendChild(el);
  });

  const tools=document.getElementById("mainPhotoTools");
  if(tools)tools.hidden=false;
}
if(input)input.addEventListener("change",e=>loadFiles(e.target.files));

async function rotatedFile(item){
  if(item.rot%360===0)return item.file;
  const img=new Image();
  img.src=item.url;
  await img.decode();
  const turns=((item.rot%360)+360)%360;
  const swap=turns===90||turns===270;
  const canvas=document.createElement("canvas");
  canvas.width=swap?img.height:img.width;
  canvas.height=swap?img.width:img.height;
  const ctx=canvas.getContext("2d");
  ctx.translate(canvas.width/2,canvas.height/2);
  ctx.rotate(turns*Math.PI/180);
  ctx.drawImage(img,-img.width/2,-img.height/2);
  const blob=await new Promise(res=>canvas.toBlob(res,item.file.type||"image/jpeg",.92));
  return new File([blob],item.file.name,{type:blob.type,lastModified:Date.now()});
}
if(form&&input)form.addEventListener("submit",async e=>{
  if(!photoItems.length)return;
  e.preventDefault();
  const dt=new DataTransfer();
  for(const item of photoItems){
    dt.items.add(await rotatedFile(item));
  }
  input.files=dt.files;
  form.submit();
});

// Existing photos are reordered by drag. A simple tap does not open or replace the page.
document.querySelectorAll(".existing-photo").forEach(card=>{
  card.querySelector("img")?.setAttribute("draggable","false");
});

(function(){
  const wrap=document.getElementById("galleryMain");
  const img=document.getElementById("detailMain");
  const thumbs=[...document.querySelectorAll("#galleryThumbs button")];
  if(!wrap||!img||!thumbs.length)return;
  let index=0,sx=null,sy=null;
  function show(i){
    index=(i+thumbs.length)%thumbs.length;
    img.src=thumbs[index].dataset.src;
    thumbs.forEach(x=>x.classList.remove("active"));
    thumbs[index].classList.add("active");
    const c=document.getElementById("galleryCurrent"); if(c)c.textContent=index+1;
  }
  document.querySelector(".gallery-prev")?.addEventListener("click",()=>show(index-1));
  document.querySelector(".gallery-next")?.addEventListener("click",()=>show(index+1));
  thumbs.forEach((b,i)=>b.addEventListener("click",()=>show(i)));
  wrap.addEventListener("touchstart",e=>{if(e.touches.length===1){sx=e.touches[0].clientX;sy=e.touches[0].clientY}},{passive:true});
  wrap.addEventListener("touchend",e=>{if(sx===null||!e.changedTouches.length)return;const dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;sx=sy=null;if(Math.abs(dx)>=45&&Math.abs(dx)>Math.abs(dy))show(dx<0?index+1:index-1)},{passive:true});
  document.addEventListener("keydown",e=>{if(e.key==="ArrowRight")show(index+1);if(e.key==="ArrowLeft")show(index-1)});
})();

// Live listing-form validation: description 20–500 and publish button activation.
const desc=document.getElementById("descriptionInput");
const descCounter=document.getElementById("descriptionCounter");
const publishBtn=document.getElementById("publishBtn");
function updateDescriptionCounter(){
  if(!desc||!descCounter)return;
  const n=desc.value.length;
  const ru=document.documentElement.lang==="ru";
  if(n<20){
    descCounter.textContent=ru
      ? `${n} / 500 · минимум 20 · осталось ${20-n}`
      : `${n} / 500 · мінімум 20 · залишилось ${20-n}`;
    descCounter.className="description-counter short";
  }else if(n>450){
    descCounter.textContent=`✓ ${n} / 500`;
    descCounter.className="description-counter near-limit";
  }else{
    descCounter.textContent=`✓ ${n} / 500`;
    descCounter.className="description-counter ok";
  }
}
function updatePublishState(){
  if(!form)return;
  const publishBtn=document.getElementById("publishBtn");
  if(!publishBtn)return;
  updateDescriptionCounter();

  let ready=true;
  form.querySelectorAll("[required]").forEach(el=>{
    if(el.id==="photoInput")return;
    const val=String(el.value ?? "").trim();
    if(!val || !el.checkValidity()) ready=false;
    if(el.name==="price"){
      const kind=form.querySelector('[name="kind"]')?.value;
      if(kind==="sale" && Number(el.value)<=0) ready=false;
    }
  });

  if(desc){
    const n=desc.value.trim().length;
    if(n<20 || n>500) ready=false;
  }

  const existingCount=form.querySelectorAll('input[name="keep_image"]').length;
  const newCount=(typeof photoItems!=="undefined" ? photoItems.length : 0);
  const totalPhotos=existingCount+newCount;
  if(totalPhotos<1 || totalPhotos>5) ready=false;

  publishBtn.disabled=!ready;
  publishBtn.classList.toggle("is-not-ready",!ready);
  publishBtn.classList.toggle("is-ready",ready);
  publishBtn.setAttribute("aria-disabled", ready ? "false" : "true");
}
if(form){
  form.addEventListener("input",updatePublishState);
  form.addEventListener("change",updatePublishState);
  updatePublishState();
}

// Existing photo editing: clear delete + rotation controls.
document.querySelectorAll(".existing-photo").forEach(card=>{
  let rot=0;
  const img=card.querySelector(".existing-img");
  const rotInput=card.querySelector(".rotation-existing");
  const sync=()=>{img.style.transform=`rotate(${rot}deg)`; if(rotInput)rotInput.value=((rot%360)+360)%360};
  card.querySelector(".rotate-existing-left")?.addEventListener("click",e=>{e.stopPropagation();rot-=90;sync()});
  card.querySelector(".rotate-existing-right")?.addEventListener("click",e=>{e.stopPropagation();rot+=90;sync()});
  card.querySelector(".delete-existing")?.addEventListener("click",e=>{
    e.stopPropagation();
    card.remove();
    document.querySelectorAll(".existing-main-label").forEach(x=>x.remove());
    const first=document.querySelector(".existing-photo");
    if(first){
      const x=document.createElement("span"); x.className="existing-main-label";
      x.textContent=document.documentElement.lang==="ru"?"Главное фото":"Головне фото"; first.appendChild(x);
    }
    updatePublishState();
  });
});
document.querySelectorAll(".chat-tab").forEach(btn=>btn.addEventListener("click",()=>{
  document.querySelectorAll(".chat-tab").forEach(x=>x.classList.remove("active"));
  document.querySelectorAll(".chat-tab-panel").forEach(x=>x.classList.remove("active"));
  btn.classList.add("active"); document.getElementById(btn.dataset.tab)?.classList.add("active");
}));

// ===== v9: SMS resend timer (prototype code 1111) =====
const smsBtn=document.getElementById("sendSms");
const smsPhone=document.getElementById("smsPhone");
const smsStatus=document.getElementById("smsStatus");
let smsTimer=null;
function startSmsCountdown(seconds){
  if(!smsBtn)return;
  clearInterval(smsTimer);
  let left=seconds;
  smsBtn.disabled=true;
  const original=document.documentElement.lang==="ru"?"Отправить код повторно":"Надіслати код повторно";
  const tick=()=>{
    if(left<=0){
      clearInterval(smsTimer);smsBtn.disabled=false;smsBtn.textContent=original;
      if(smsStatus)smsStatus.textContent="";
      return;
    }
    smsBtn.textContent=(document.documentElement.lang==="ru"?"Повторно через ":"Повторно через ")+left+" с";
    left--;
  };
  tick(); smsTimer=setInterval(tick,1000);
}
smsBtn?.addEventListener("click",async()=>{
  const phone=(smsPhone?.value||"").trim();
  if(!phone){if(smsStatus)smsStatus.textContent=document.documentElement.lang==="ru"?"Введите номер телефона":"Вкажіть номер телефону";return}
  const body=new URLSearchParams({phone});
  try{
    const r=await fetch("/auth/send-code",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body});
    const data=await r.json();
    if(smsStatus)smsStatus.textContent=data.message||"";
    startSmsCountdown(data.wait||60);
  }catch(e){
    if(smsStatus)smsStatus.textContent=document.documentElement.lang==="ru"?"Не удалось отправить код":"Не вдалося надіслати код";
  }
});

// ===== v9: chat photo/camera preview =====
const chatForm=document.getElementById("chatMessageForm");
const chatImage=document.getElementById("chatImageInput");
const chatCamera=document.getElementById("chatCameraInput");
const chatPreview=document.getElementById("chatPreview");
const chatPreviewImg=document.getElementById("chatPreviewImg");
const removeChatPhoto=document.getElementById("removeChatPhoto");
const retakeChatPhoto=document.getElementById("retakeChatPhoto");
let chatSource=null;
function showChatPreview(input,source){
  const file=input?.files?.[0];
  if(!file)return;
  chatSource=source;
  if(source==="gallery" && chatCamera) chatCamera.value="";
  if(source==="camera" && chatImage) chatImage.value="";
  const r=new FileReader();
  r.onload=()=>{
    if(chatPreviewImg)chatPreviewImg.src=r.result;
    if(chatPreview)chatPreview.hidden=false;
    if(retakeChatPhoto)retakeChatPhoto.hidden=source!=="camera";
  };
  r.readAsDataURL(file);
}
chatImage?.addEventListener("change",()=>showChatPreview(chatImage,"gallery"));
chatCamera?.addEventListener("change",()=>showChatPreview(chatCamera,"camera"));
removeChatPhoto?.addEventListener("click",()=>{
  if(chatImage)chatImage.value="";
  if(chatCamera)chatCamera.value="";
  if(chatPreview)chatPreview.hidden=true;
  if(chatPreviewImg){ chatPreviewImg.src=""; chatPreviewImg.removeAttribute("src"); }
  if(retakeChatPhoto)retakeChatPhoto.hidden=true;
  chatSource=null;
});
retakeChatPhoto?.addEventListener("click",()=>chatCamera?.click());
chatForm?.addEventListener("submit",e=>{
  const text=(chatForm.querySelector('textarea[name="text"]')?.value||"").trim();
  const hasImage=!!(chatImage?.files?.length||chatCamera?.files?.length);
  if(!text&&!hasImage){
    e.preventDefault();
    alert(document.documentElement.lang==="ru"?"Напишите сообщение или добавьте фото.":"Напишіть повідомлення або додайте фото.");
  }
});

// ===== v28: reorder existing photos; first card is main =====
(function(){
  const box=document.getElementById("existingPhotos");
  if(!box)return;
  let dragged=null;
  let pointerCard=null;
  let pointerId=null;
  let moved=false;

  const markMain=()=>{
    box.querySelectorAll(".existing-main-label").forEach(x=>x.remove());
    box.querySelectorAll(".existing-photo").forEach(x=>x.classList.remove("selected"));
    const first=box.querySelector(".existing-photo");
    if(first){
      first.classList.add("selected");
      const x=document.createElement("span");
      x.className="existing-main-label";
      x.textContent=document.documentElement.lang==="ru"?"Главное фото":"Головне фото";
      first.appendChild(x);
    }
    if(typeof updatePublishState==="function") updatePublishState();
  };

  const cards=()=>[...box.querySelectorAll(".existing-photo")];

  cards().forEach(card=>{
    const img=card.querySelector(".existing-img");
    if(img){img.draggable=false; img.style.webkitUserDrag="none";}

    // Desktop mouse drag only.
    card.draggable=window.matchMedia?.("(pointer:fine)")?.matches ?? true;
    card.addEventListener("dragstart",e=>{
      dragged=card;
      card.classList.add("dragging");
      e.dataTransfer.effectAllowed="move";
    });
    card.addEventListener("dragend",()=>{
      dragged=null;
      card.classList.remove("dragging");
      markMain();
    });
    card.addEventListener("dragover",e=>{
      if(!dragged||dragged===card)return;
      e.preventDefault();
      const r=card.getBoundingClientRect();
      box.insertBefore(dragged,e.clientX<r.left+r.width/2?card:card.nextSibling);
    });

    // Touch/pointer reorder. Prevent native iOS image drag/preview.
    card.addEventListener("pointerdown",e=>{
      if(e.pointerType==="mouse" || e.target.closest("button"))return;
      e.preventDefault();
      pointerCard=card;
      pointerId=e.pointerId;
      moved=false;
      card.setPointerCapture?.(e.pointerId);
      card.classList.add("dragging");
    },{passive:false});

    card.addEventListener("pointermove",e=>{
      if(!pointerCard || e.pointerId!==pointerId)return;
      e.preventDefault();
      moved=true;
      const target=document.elementFromPoint(e.clientX,e.clientY)?.closest?.(".existing-photo");
      if(target && target!==pointerCard && target.parentElement===box){
        const r=target.getBoundingClientRect();
        box.insertBefore(pointerCard,e.clientX<r.left+r.width/2?target:target.nextSibling);
      }
    },{passive:false});

    const finish=e=>{
      if(!pointerCard || (e.pointerId!=null && e.pointerId!==pointerId))return;
      e.preventDefault?.();
      pointerCard.classList.remove("dragging");
      pointerCard=null; pointerId=null;
      markMain();
      setTimeout(()=>{moved=false},0);
    };
    card.addEventListener("pointerup",finish,{passive:false});
    card.addEventListener("pointercancel",finish,{passive:false});
    card.addEventListener("click",e=>{
      if(moved){e.preventDefault();e.stopPropagation();}
    },true);
  });

  markMain();
})();

// ===== v11: city fields start with capital letters =====
function normalizeCityText(value){
  return value.trim().replace(/\s+/g," ").split(" ").map(word =>
    word.split("-").map(part => part ? part.charAt(0).toLocaleUpperCase()+part.slice(1) : part).join("-")
  ).join(" ");
}
document.querySelectorAll('input[name="city"]').forEach(input=>{
  input.setAttribute("autocapitalize","words");
  input.addEventListener("blur",()=>{ input.value=normalizeCityText(input.value); });
});

// ===== v12: robust active state for "Шукаю конкретне" =====
if(location.pathname.startsWith("/wanted")){
  document.querySelector(".search-specific")?.classList.add("active-wanted");
}


// ===== v15: reliable logo lightbox =====
(function(){
  const openBtn=document.getElementById("openLogoModal");
  const box=document.getElementById("logoLightbox");
  const closeBtn=document.getElementById("closeLogoModal");
  if(!openBtn || !box) return;

  const open=()=>{
    box.hidden=false;
    document.body.classList.add("logo-modal-open");
    closeBtn?.focus();
  };
  const close=()=>{
    box.hidden=true;
    document.body.classList.remove("logo-modal-open");
    openBtn.focus();
  };

  openBtn.addEventListener("click",e=>{e.preventDefault();e.stopPropagation();open();});
  closeBtn?.addEventListener("click",close);
  box.addEventListener("click",e=>{if(e.target===box)close();});
  document.addEventListener("keydown",e=>{if(e.key==="Escape" && !box.hidden)close();});
})();

// ===== v18 avatar crop: real mouse/touch dragging =====
(function(){
  const modal = document.getElementById("avatarCropModal");
  const fileInput = document.getElementById("avatarFileInput");
  const submitFile = document.getElementById("avatarSubmitFile");
  const img = document.getElementById("avatarCropImage");
  const viewport = document.getElementById("avatarCropViewport");
  const closeBtn = document.getElementById("avatarCropClose");
  const adjustBtn = document.getElementById("adjustAvatarBtn");
  const zoomRange = document.getElementById("avatarZoomRange");
  if(!modal || !img || !viewport || !zoomRange) return;

  let sourceMode = "existing";
  let zoom = 1;
  let offsetX = 0;   // pixels relative to viewport center
  let offsetY = 0;
  let dragging = false;
  let pointerId = null;
  let dragStartX = 0, dragStartY = 0;
  let startOffsetX = 0, startOffsetY = 0;

  const existingAvatarNode = document.querySelector(".profile-avatar-img");
  const existingSrc = existingAvatarNode?.dataset?.avatarOriginal || existingAvatarNode?.querySelector("img")?.src || "";
  const existingNode = document.querySelector(".profile-avatar-img");

  function getCssNumber(name, fallback){
    if(!existingNode) return fallback;
    const v = getComputedStyle(existingNode).getPropertyValue(name).trim();
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : fallback;
  }

  function clampOffsets(){
    const rect = viewport.getBoundingClientRect();
    const maxX = rect.width * 0.42 * zoom;
    const maxY = rect.height * 0.42 * zoom;
    offsetX = Math.max(-maxX, Math.min(maxX, offsetX));
    offsetY = Math.max(-maxY, Math.min(maxY, offsetY));
  }

  function syncHidden(){
    const rect = viewport.getBoundingClientRect();
    const xPercent = rect.width ? 50 + (offsetX / rect.width) * 100 : 50;
    const yPercent = rect.height ? 50 + (offsetY / rect.height) * 100 : 50;
    const x = Math.max(0, Math.min(100, xPercent));
    const y = Math.max(0, Math.min(100, yPercent));

    ["avatarXNew","avatarXExisting"].forEach(id=>{
      const el=document.getElementById(id); if(el) el.value=x;
    });
    ["avatarYNew","avatarYExisting"].forEach(id=>{
      const el=document.getElementById(id); if(el) el.value=y;
    });
    ["avatarZoomNew","avatarZoomExisting"].forEach(id=>{
      const el=document.getElementById(id); if(el) el.value=zoom;
    });
  }

  function render(){
    clampOffsets();
    img.style.width = (100 * zoom) + "%";
    img.style.height = (100 * zoom) + "%";
    img.style.objectFit = "cover";
    img.style.objectPosition = "50% 50%";
    img.style.transform = `translate(calc(-50% + ${offsetX}px), calc(-50% + ${offsetY}px))`;

    const newForm = document.getElementById("avatarUploadForm");
    const existingForm = document.getElementById("avatarSettingsForm");
    if(newForm) newForm.style.display = sourceMode==="new" ? "inline-block" : "none";
    if(existingForm) existingForm.style.display = sourceMode==="existing" ? "inline-block" : "none";
    syncHidden();
  }

  function setExistingFromSaved(){
    // Convert saved object-position percentages back into approximate pixel offsets.
    const rect = viewport.getBoundingClientRect();
    const x = getCssNumber("--avatar-x", 50);
    const y = getCssNumber("--avatar-y", 50);
    zoom = Math.max(1, Math.min(3, getCssNumber("--avatar-zoom", 1)));
    offsetX = ((x - 50) / 100) * (rect.width || 300);
    offsetY = ((y - 50) / 100) * (rect.height || 300);
  }

  function openExisting(){
    if(!existingSrc) return;
    sourceMode="existing";
    img.src=existingSrc;
    modal.hidden=false;
    requestAnimationFrame(()=>{
      setExistingFromSaved();
      zoomRange.value=zoom;
      render();
    });
  }

  function openNew(file){
    sourceMode="new";
    zoom=1; offsetX=0; offsetY=0;
    const dt=new DataTransfer(); dt.items.add(file); submitFile.files=dt.files;
    const r=new FileReader();
    r.onload=()=>{
      img.src=r.result;
      modal.hidden=false;
      zoomRange.value=1;
      requestAnimationFrame(render);
    };
    r.readAsDataURL(file);
  }

  fileInput?.addEventListener("change",()=>{
    const f=fileInput.files?.[0];
    if(f) openNew(f);
  });
  adjustBtn?.addEventListener("click",openExisting);
  closeBtn?.addEventListener("click",()=>modal.hidden=true);
  modal.addEventListener("click",e=>{ if(e.target===modal) modal.hidden=true; });
  document.addEventListener("keydown",e=>{ if(e.key==="Escape" && !modal.hidden) modal.hidden=true; });

  zoomRange.addEventListener("input",()=>{
    zoom = parseFloat(zoomRange.value) || 1;
    render();
  });

  // IMPORTANT: drag is attached to the viewport itself and works with mouse + touch/pen.
  viewport.addEventListener("pointerdown", e=>{
    e.preventDefault();
    dragging=true;
    pointerId=e.pointerId;
    dragStartX=e.clientX;
    dragStartY=e.clientY;
    startOffsetX=offsetX;
    startOffsetY=offsetY;
    viewport.setPointerCapture?.(pointerId);
    viewport.classList.add("is-dragging");
  });

  viewport.addEventListener("pointermove", e=>{
    if(!dragging || e.pointerId!==pointerId) return;
    e.preventDefault();
    offsetX = startOffsetX + (e.clientX - dragStartX);
    offsetY = startOffsetY + (e.clientY - dragStartY);
    render();
  });

  function finishDrag(e){
    if(!dragging) return;
    if(e && pointerId!==null && e.pointerId!==pointerId) return;
    dragging=false;
    viewport.classList.remove("is-dragging");
    try{ viewport.releasePointerCapture?.(pointerId); }catch(_){}
    pointerId=null;
    render();
  }
  viewport.addEventListener("pointerup",finishDrag);
  viewport.addEventListener("pointercancel",finishDrag);
  viewport.addEventListener("lostpointercapture",()=>finishDrag());

  // Fallback for browsers where Pointer Events are flaky.
  viewport.addEventListener("mousedown", e=>{
    if(window.PointerEvent) return;
    e.preventDefault();
    dragging=true;
    dragStartX=e.clientX; dragStartY=e.clientY;
    startOffsetX=offsetX; startOffsetY=offsetY;
  });
  window.addEventListener("mousemove", e=>{
    if(window.PointerEvent || !dragging) return;
    offsetX=startOffsetX+(e.clientX-dragStartX);
    offsetY=startOffsetY+(e.clientY-dragStartY);
    render();
  });
  window.addEventListener("mouseup", ()=>{
    if(window.PointerEvent) return;
    dragging=false;
  });
})();


// ===== v19 circular high-resolution avatar viewer =====
(function(){
  const viewer=document.getElementById("avatarViewer");
  const viewerImg=document.getElementById("avatarViewerImage");
  const viewerCircle=document.getElementById("avatarViewerCircle");
  const closeBtn=document.getElementById("avatarViewerClose");
  if(!viewer||!viewerImg||!viewerCircle)return;

  function close(){
    viewer.hidden=true;
    viewerImg.removeAttribute("src");
    document.body.classList.remove("avatar-viewer-open");
  }

  document.addEventListener("click",e=>{
    const avatar=e.target.closest?.("[data-avatar-preview]");
    if(!avatar)return;
    const source=avatar.querySelector("img");
    if(!source?.src)return;
    e.preventDefault();
    e.stopPropagation();

    const style=getComputedStyle(avatar);
    const x=style.getPropertyValue("--avatar-x").trim() || "50%";
    const y=style.getPropertyValue("--avatar-y").trim() || "50%";
    const zoom=style.getPropertyValue("--avatar-zoom").trim() || "1";

    viewerCircle.style.setProperty("--avatar-x",x);
    viewerCircle.style.setProperty("--avatar-y",y);
    viewerCircle.style.setProperty("--avatar-zoom",zoom);
    viewerImg.src=source.currentSrc || source.src;
    viewer.hidden=false;
    document.body.classList.add("avatar-viewer-open");
    closeBtn?.focus();
  },true);

  closeBtn?.addEventListener("click",close);
  viewer.addEventListener("click",e=>{if(e.target===viewer)close();});
  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!viewer.hidden)close();});
})();

// ===== v22 dynamic listing type fields =====
(function(){
  const form=document.getElementById("listingForm");
  if(!form)return;
  const kind=form.querySelector('select[name="kind"]');
  const priceField=document.getElementById("priceField");
  const priceInput=priceField?.querySelector('input[name="price"]');
  const exchangeOptions=document.getElementById("exchangeOptions");
  const exchangeType=document.getElementById("exchangeType");
  const exchangeOtherField=document.getElementById("exchangeOtherField");

  function syncExchangeOther(){
    if(!exchangeOtherField)return;
    exchangeOtherField.hidden=!(exchangeType?.value==="other");
  }

  function syncKind(){
    const value=kind?.value || "sale";
    const sale=value==="sale";
    const exchange=value==="exchange";

    if(priceField) priceField.hidden=!sale;
    if(priceInput){
      priceInput.required=sale;
      if(!sale) priceInput.value="";
    }

    if(exchangeOptions) exchangeOptions.hidden=!exchange;
    exchangeOptions?.querySelectorAll("input,select,textarea").forEach(el=>{
      el.disabled=!exchange;
    });

    syncExchangeOther();
    if(typeof updatePublishState==="function") updatePublishState();
  }

  kind?.addEventListener("change",syncKind);
  exchangeType?.addEventListener("change",syncExchangeOther);
  syncKind();
})();

// ===== v23 profile nickname editor =====
(function(){
  const open=document.getElementById("editNameBtn");
  const box=document.getElementById("profileNameEdit");
  const cancel=document.getElementById("cancelNameEdit");
  open?.addEventListener("click",()=>{box.hidden=false;box.querySelector("input")?.focus();});
  cancel?.addEventListener("click",()=>{box.hidden=true;});
})();

// ===== v23 exchange offer mini photo editor =====
(function(){
  const input=document.getElementById("exchangePhotoInput");
  const strip=document.getElementById("exchangePhotoStrip");
  const form=document.getElementById("exchangeOfferForm");
  if(!input||!strip||!form)return;

  let items=[];
  let dragIndex=null;

  function readFile(file){
    return new Promise((resolve,reject)=>{
      const r=new FileReader();
      r.onload=()=>resolve(r.result);
      r.onerror=reject;
      r.readAsDataURL(file);
    });
  }

  async function addFiles(files){
    const remaining=Math.max(0,5-items.length);
    const selected=[...files].slice(0,remaining);
    for(const f of selected){
      items.push({file:f,url:await readFile(f),rot:0});
    }
    input.value="";
    render();
  }

  function move(from,to){
    if(from===to||from<0||to<0||from>=items.length||to>=items.length)return;
    const x=items.splice(from,1)[0];
    items.splice(to,0,x);
    render();
  }

  function render(){
    strip.innerHTML="";
    items.forEach((item,i)=>{
      const card=document.createElement("div");
      card.className="exchange-photo-item";
      card.draggable=true;
      card.innerHTML=`<img src="${item.url}" style="transform:rotate(${item.rot}deg)">
        <div class="exchange-photo-tools">
          <button type="button" data-a="left">↺</button>
          <button type="button" data-a="right">↻</button>
          <button type="button" data-a="del">×</button>
        </div>
        ${i===0?'<span class="exchange-main-photo">1</span>':''}`;

      card.addEventListener("dragstart",()=>{dragIndex=i;card.classList.add("dragging")});
      card.addEventListener("dragend",()=>{dragIndex=null;card.classList.remove("dragging")});
      card.addEventListener("dragover",e=>e.preventDefault());
      card.addEventListener("drop",e=>{e.preventDefault();if(dragIndex!==null)move(dragIndex,i)});

      card.querySelector('[data-a="left"]').onclick=()=>{item.rot=(item.rot-90)%360;render()};
      card.querySelector('[data-a="right"]').onclick=()=>{item.rot=(item.rot+90)%360;render()};
      card.querySelector('[data-a="del"]').onclick=()=>{items.splice(i,1);render()};
      strip.appendChild(card);
    });
  }

  async function rotated(item){
    const deg=((item.rot%360)+360)%360;
    if(deg===0)return item.file;
    const img=new Image();
    img.src=item.url;
    await img.decode();
    const swap=deg===90||deg===270;
    const c=document.createElement("canvas");
    c.width=swap?img.height:img.width;
    c.height=swap?img.width:img.height;
    const ctx=c.getContext("2d");
    ctx.translate(c.width/2,c.height/2);
    ctx.rotate(deg*Math.PI/180);
    ctx.drawImage(img,-img.width/2,-img.height/2);
    const blob=await new Promise(resolve=>c.toBlob(resolve,item.file.type||"image/jpeg",.94));
    return new File([blob],item.file.name,{type:blob.type,lastModified:Date.now()});
  }

  input.addEventListener("change",e=>addFiles(e.target.files));

  form.addEventListener("submit",async e=>{
    if(form.dataset.readyToSend==="1")return;
    if(!items.length){
      e.preventDefault();
      alert(document.documentElement.lang==="ru"?"Добавьте хотя бы одно фото.":"Додайте хоча б одне фото.");
      return;
    }
    e.preventDefault();
    const dt=new DataTransfer();
    for(const item of items)dt.items.add(await rotated(item));
    input.files=dt.files;
    form.dataset.readyToSend="1";
    form.requestSubmit();
  });
})();

// ===== Beta v25: favorite buttons work independently of listing links =====
(function(){
  document.querySelectorAll('form[action^="/favorite/"]').forEach(form=>{
    form.addEventListener("click",e=>e.stopPropagation());
    form.addEventListener("submit",async e=>{
      e.preventDefault();
      e.stopPropagation();
      const button=form.querySelector("button");
      try{
        const res=await fetch(form.action,{
          method:"POST",
          body:new FormData(form),
          headers:{"X-Requested-With":"XMLHttpRequest"},
          credentials:"same-origin"
        });
        if(res.redirected){location.href=res.url;return}
        const data=await res.json();
        if(data.ok){
          button.classList.toggle("is-fav",!!data.favorite);
          button.textContent=data.favorite?"♥":"♡";
          button.setAttribute("aria-pressed",data.favorite?"true":"false");
        }
      }catch(err){
        // Normal form fallback if AJAX is unavailable.
        form.submit();
      }
    });
  });
})();

// ===== Beta v30: large-photo controls affect the photo currently being previewed =====
(function(){
  const tools=document.getElementById("mainPhotoTools");
  const left=document.getElementById("mainRotateLeft");
  const right=document.getElementById("mainRotateRight");
  const del=document.getElementById("mainDeletePhoto");
  if(!tools)return;

  function sync(){
    tools.hidden=!(typeof photoItems!=="undefined" && photoItems.length && previewItem);
  }
  left?.addEventListener("click",()=>{
    if(!previewItem)return;
    previewItem.rot=(previewItem.rot-90)%360;
    renderPhotoEditor(); sync();
  });
  right?.addEventListener("click",()=>{
    if(!previewItem)return;
    previewItem.rot=(previewItem.rot+90)%360;
    renderPhotoEditor(); sync();
  });
  del?.addEventListener("click",()=>{
    if(!previewItem)return;
    const idx=photoItems.indexOf(previewItem);
    if(idx<0)return;
    photoItems.splice(idx,1);
    previewItem=photoItems[Math.min(idx,photoItems.length-1)] || photoItems[0] || null;
    renderPhotoEditor(); updatePublishState(); sync();
  });
  sync();
})();

// ===== Beta v26 =====
// Password visibility buttons
document.querySelectorAll("[data-password-toggle]").forEach(btn=>btn.addEventListener("click",()=>{
 const input=document.getElementById(btn.dataset.passwordToggle); if(!input)return;
 const show=input.type==="password"; input.type=show?"text":"password"; btn.classList.toggle("active",show);
}));
// Email beta verification code
document.getElementById("sendEmailCode")?.addEventListener("click",async()=>{
 const email=document.getElementById("authEmail")?.value.trim(); const status=document.getElementById("emailCodeStatus");
 if(!email){status.textContent=document.documentElement.lang==="ru"?"Введите электронную почту":"Вкажіть електронну пошту";return}
 const body=new URLSearchParams({email});
 try{const r=await fetch("/auth/send-code",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body}); const d=await r.json();status.textContent=d.message||""}catch(e){status.textContent="Error"}
});
// Price accepts digits only and opens numeric keyboard on phones.
document.querySelectorAll(".digits-only").forEach(input=>input.addEventListener("input",()=>{input.value=input.value.replace(/\D/g,"")}));



// ===== Beta v28: iOS/Android friendly city autocomplete =====
(async function(){
  const input=document.getElementById("listingCity");
  const box=document.getElementById("citySuggestions");
  const toggle=document.getElementById("cityDropdownToggle");
  if(!input||!box)return;

  let cities=[];
  let selectedCanonical=(input.value||"").trim();

  try{
    const response=await fetch("/static/ukraine_cities.json",{cache:"no-store"});
    if(!response.ok)throw new Error("cities");
    cities=await response.json();
  }catch(e){
    input.setCustomValidity(document.documentElement.lang==="ru"?"Не удалось загрузить список городов":"Не вдалося завантажити список міст");
    return;
  }

  const norm=s=>(s||"").trim().toLocaleLowerCase("uk-UA");
  const byName=new Map(cities.map(c=>[norm(c.name),c]));

  function choose(city){
    input.value=city.name;
    selectedCanonical=city.name;
    input.setCustomValidity("");
    box.hidden=true;
    input.dispatchEvent(new Event("input",{bubbles:true}));
    input.dispatchEvent(new Event("change",{bubbles:true}));
  }

  function render(query="",showAll=false){
    const q=norm(query);
    let matches=cities;
    if(!showAll && q){
      const starts=[], contains=[];
      cities.forEach(c=>{
        const n=norm(c.name);
        if(n.startsWith(q))starts.push(c);
        else if(n.includes(q))contains.push(c);
      });
      matches=[...starts,...contains];
    }
    matches=matches.slice(0,showAll?80:20);
    box.innerHTML="";
    if(!matches.length){
      const empty=document.createElement("span");
      empty.className="city-suggestion-empty";
      empty.textContent=document.documentElement.lang==="ru"?"Город не найден":"Місто не знайдено";
      box.appendChild(empty);
      box.hidden=false;
      return;
    }
    matches.forEach(c=>{
      const btn=document.createElement("button");
      btn.type="button";
      btn.className="city-suggestion";
      btn.innerHTML=`<b>${c.name}</b><small>${c.region||""}</small>`;
      btn.addEventListener("pointerdown",e=>e.preventDefault());
      btn.addEventListener("click",()=>choose(c));
      box.appendChild(btn);
    });
    box.hidden=false;
  }

  input.addEventListener("focus",()=>render(input.value,false));
  input.addEventListener("input",()=>{
    selectedCanonical="";
    input.setCustomValidity("");
    render(input.value,false);
  });
  input.addEventListener("blur",()=>{
    setTimeout(()=>{
      const exact=byName.get(norm(input.value));
      if(exact){
        input.value=exact.name;
        selectedCanonical=exact.name;
        input.setCustomValidity("");
      }else if(input.value.trim()){
        input.setCustomValidity(document.documentElement.lang==="ru"?"Выберите город из предложенного списка":"Оберіть місто із запропонованого списку");
      }
      box.hidden=true;
    },180);
  });
  toggle?.addEventListener("click",()=>{
    input.focus();
    render("",true);
  });
  input.form?.addEventListener("submit",e=>{
    const exact=byName.get(norm(input.value));
    if(!exact){
      input.setCustomValidity(document.documentElement.lang==="ru"?"Выберите город из предложенного списка":"Оберіть місто із запропонованого списку");
      input.reportValidity();
      e.preventDefault();
      return;
    }
    input.value=exact.name;
  });
})();


// ===== Beta v28: password recovery uses email too =====
document.getElementById("sendForgotEmailCode")?.addEventListener("click",async()=>{
  const email=document.getElementById("forgotEmail")?.value.trim();
  const status=document.getElementById("forgotEmailCodeStatus");
  if(!email){
    if(status)status.textContent=document.documentElement.lang==="ru"?"Введите электронную почту":"Вкажіть електронну пошту";
    return;
  }
  const body=new URLSearchParams({email});
  try{
    const r=await fetch("/auth/send-code",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body});
    const d=await r.json();
    if(status)status.textContent=d.message||"";
  }catch(e){
    if(status)status.textContent=document.documentElement.lang==="ru"?"Не удалось получить код":"Не вдалося отримати код";
  }
});


// ===== Beta v29: full-screen original photo viewer =====
(function(){
  const gallery=document.getElementById("galleryMain");
  const main=document.getElementById("detailMain");
  const thumbs=[...document.querySelectorAll("#galleryThumbs button")];
  const viewer=document.getElementById("listingPhotoViewer");
  const viewerImg=document.getElementById("listingPhotoViewerImage");
  const close=document.getElementById("listingPhotoViewerClose");
  const prev=viewer?.querySelector(".viewer-prev");
  const next=viewer?.querySelector(".viewer-next");
  const counter=document.getElementById("listingPhotoViewerCurrent");
  if(!gallery||!main||!viewer||!viewerImg||!thumbs.length)return;

  let index=0;

  function currentIndex(){
    const active=thumbs.findIndex(x=>x.classList.contains("active"));
    return active>=0?active:0;
  }

  function show(i){
    index=(i+thumbs.length)%thumbs.length;
    viewerImg.src=thumbs[index].dataset.src;
    if(counter)counter.textContent=index+1;
  }

  function open(){
    show(currentIndex());
    viewer.hidden=false;
    document.body.classList.add("listing-photo-viewer-open");
    close?.focus();
  }

  function hide(){
    viewer.hidden=true;
    viewerImg.removeAttribute("src");
    document.body.classList.remove("listing-photo-viewer-open");
  }

  // Only tapping the actual large image opens full-screen. Arrows keep their normal behavior.
  main.addEventListener("click",e=>{
    e.preventDefault();
    e.stopPropagation();
    open();
  });

  close?.addEventListener("click",hide);
  prev?.addEventListener("click",()=>show(index-1));
  next?.addEventListener("click",()=>show(index+1));
  viewer.addEventListener("click",e=>{if(e.target===viewer)hide();});

  let sx=null,sy=null;
  viewer.addEventListener("touchstart",e=>{
    if(e.touches.length===1){sx=e.touches[0].clientX;sy=e.touches[0].clientY}
  },{passive:true});
  viewer.addEventListener("touchend",e=>{
    if(sx===null||!e.changedTouches.length)return;
    const dx=e.changedTouches[0].clientX-sx;
    const dy=e.changedTouches[0].clientY-sy;
    sx=sy=null;
    if(Math.abs(dx)>45 && Math.abs(dx)>Math.abs(dy))show(dx<0?index+1:index-1);
  },{passive:true});

  document.addEventListener("keydown",e=>{
    if(viewer.hidden)return;
    if(e.key==="Escape")hide();
    if(e.key==="ArrowLeft")show(index-1);
    if(e.key==="ArrowRight")show(index+1);
  });
})();
