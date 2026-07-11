"""Bidirectional Streamlit v2 C/K plane + native browser color picker."""
from __future__ import annotations

from collections.abc import Callable

import streamlit as st

_HTML = """
<div class="ink-picker">
  <div class="ink-picker__header">
    <div>
      <strong id="label">Ink</strong>
      <div class="ink-picker__hint">Drag the plane: Cyan → · Black ↓</div>
    </div>
    <label class="ink-picker__native">
      Browser color
      <input id="native-color" type="color" />
    </label>
  </div>
  <canvas id="plane" width="520" height="300" aria-label="Cyan and black color plane"></canvas>
  <div class="ink-picker__readout" id="readout"></div>
</div>
"""

_CSS = """
.ink-picker {
  font-family: var(--st-font);
  color: var(--st-text-color);
  border: 1px solid var(--st-border-color);
  border-radius: var(--st-base-radius);
  padding: 0.85rem;
  background: var(--st-secondary-background-color);
}
.ink-picker__header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 1rem;
  margin-bottom: 0.65rem;
}
.ink-picker__hint { opacity: 0.65; font-size: 0.78rem; margin-top: 0.15rem; }
.ink-picker__native {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.78rem;
  white-space: nowrap;
}
.ink-picker__native input {
  width: 3rem;
  height: 2rem;
  padding: 0;
  border: 1px solid var(--st-border-color);
  border-radius: 0.3rem;
  background: transparent;
  cursor: pointer;
}
#plane {
  display: block;
  width: 100%;
  height: 300px;
  border-radius: 0.35rem;
  cursor: crosshair;
  touch-action: none;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.16);
}
.ink-picker__readout {
  margin-top: 0.6rem;
  font-family: var(--st-code-font);
  font-size: 0.78rem;
}
"""

_JS = """
export default function ({ parentElement, data, setStateValue }) {
  const canvas = parentElement.querySelector('#plane');
  const ctx = canvas.getContext('2d');
  const readout = parentElement.querySelector('#readout');
  const colorInput = parentElement.querySelector('#native-color');
  const label = parentElement.querySelector('#label');
  let recipe = Array.isArray(data?.recipe) ? data.recipe.map(Number) : [0, 0, 0, 0];
  label.textContent = data?.label || 'Ink';

  const clamp = (value) => Math.max(0, Math.min(100, Math.round(value)));
  const cmykToRgb = ([c,m,y,k]) => {
    const C=c/100, M=m/100, Y=y/100, K=k/100;
    return [
      Math.round(255*(1-C)*(1-K)),
      Math.round(255*(1-M)*(1-K)),
      Math.round(255*(1-Y)*(1-K)),
    ];
  };
  const rgbToCmyk = (r,g,b) => {
    const R=r/255, G=g/255, B=b/255;
    const K=1-Math.max(R,G,B);
    if (K >= 0.999999) return [0,0,0,100];
    return [
      clamp(((1-R-K)/(1-K))*100),
      clamp(((1-G-K)/(1-K))*100),
      clamp(((1-B-K)/(1-K))*100),
      clamp(K*100),
    ];
  };
  const toHex = (rgb) => '#' + rgb.map(v => v.toString(16).padStart(2,'0')).join('');
  const fromHex = (hex) => [
    parseInt(hex.slice(1,3),16),
    parseInt(hex.slice(3,5),16),
    parseInt(hex.slice(5,7),16),
  ];

  let planeImage;
  function drawPlane() {
    const width=canvas.width, height=canvas.height;
    const image=ctx.createImageData(width,height);
    const m=recipe[1], y=recipe[2];
    for (let py=0; py<height; py++) {
      const k=(py/(height-1))*100;
      for (let px=0; px<width; px++) {
        const c=(px/(width-1))*100;
        const [r,g,b]=cmykToRgb([c,m,y,k]);
        const i=(py*width+px)*4;
        image.data[i]=r; image.data[i+1]=g; image.data[i+2]=b; image.data[i+3]=255;
      }
    }
    planeImage=image;
  }
  function paint() {
    const width=canvas.width, height=canvas.height;
    ctx.putImageData(planeImage,0,0);
    const markerX=(recipe[0]/100)*(width-1);
    const markerY=(recipe[3]/100)*(height-1);
    ctx.beginPath(); ctx.arc(markerX,markerY,8,0,Math.PI*2);
    ctx.lineWidth=3; ctx.strokeStyle='#ffffff'; ctx.stroke();
    ctx.beginPath(); ctx.arc(markerX,markerY,5.5,0,Math.PI*2);
    ctx.lineWidth=2; ctx.strokeStyle='#111827'; ctx.stroke();
    const hex=toHex(cmykToRgb(recipe));
    colorInput.value=hex;
    readout.textContent=`C${recipe[0]} M${recipe[1]} Y${recipe[2]} K${recipe[3]} · ${hex}`;
  }

  function fromPointer(event, commit=false) {
    const rect=canvas.getBoundingClientRect();
    recipe[0]=clamp(((event.clientX-rect.left)/rect.width)*100);
    recipe[3]=clamp(((event.clientY-rect.top)/rect.height)*100);
    paint();
    if (commit) setStateValue('recipe', recipe.slice());
  }
  let dragging=false;
  canvas.onpointerdown=(event) => { dragging=true; canvas.setPointerCapture(event.pointerId); fromPointer(event); };
  canvas.onpointermove=(event) => { if (dragging) fromPointer(event); };
  canvas.onpointerup=(event) => { if (!dragging) return; dragging=false; fromPointer(event,true); };
  canvas.onpointercancel=() => { dragging=false; };
  colorInput.onchange=(event) => {
    const [r,g,b]=fromHex(event.target.value);
    recipe=rgbToCmyk(r,g,b);
    drawPlane();
    paint();
    setStateValue('recipe', recipe.slice());
  };
  drawPlane();
  paint();
}
"""

_COMPONENT = None
_components = getattr(st, "components", None)
if _components is not None and hasattr(_components, "v2"):
    _COMPONENT = _components.v2.component(
        "phacker_ck_ink_picker",
        html=_HTML,
        css=_CSS,
        js=_JS,
    )


def ck_ink_picker(
    label: str,
    recipe: list[int],
    *,
    key: str,
    on_change: Callable[[], None],
):
    """Mount the real JS picker. Streamlit <1.58 gets a graceful test fallback."""
    if _COMPONENT is None:
        st.info("Interactive color plane requires Streamlit 1.58+; exact sliders remain available.")
        return None
    return _COMPONENT(
        data={"label": label, "recipe": recipe},
        default={"recipe": recipe},
        key=key,
        on_recipe_change=on_change,
    )
