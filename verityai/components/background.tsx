"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

// Reads a daisyUI theme color (e.g. "--color-success") and returns it as sRGB 0-1.
// Drawing it to a 1px canvas lets the browser convert oklch() for us.
function themeColor(variable: string, fallback: string) {
  const value =
    getComputedStyle(document.documentElement).getPropertyValue(variable).trim() || fallback;
  const ctx = document.createElement("canvas").getContext("2d");
  if (!ctx) return new THREE.Vector3(0.2, 0.85, 0.6);
  ctx.fillStyle = value;
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
  return new THREE.Vector3(r / 255, g / 255, b / 255);
}

// Same base wave as the shader, so the cursor point can hover just above the surface
function waveHeight(x: number, z: number, t: number) {
  let h =
    Math.sin(x * 0.22 + t * 0.6) * 0.9 +
    Math.sin(z * 0.28 + t * 0.45) * 0.7 +
    Math.sin((x + z) * 0.12 + t * 0.8) * 0.6;
  const d = Math.hypot(x, z);
  h += Math.sin(d * 0.6 - t * 1.6) * 0.35 * Math.exp(-d * 0.04);
  return h;
}

const RIPPLES = 5;
const RIPPLE_LIFE = 3.5;
const RIPPLE_SPEED = 7;

const waveVertex = /* glsl */ `
  uniform float uTime;
  uniform float uPixelRatio;
  uniform vec2 uMouse;
  uniform float uStrength;
  uniform vec4 uRipples[${RIPPLES}]; // x, z, start time, amplitude
  varying float vHeight;
  varying float vDepth;
  varying float vGlow;
  varying float vRing;
  varying float vScan;
  varying float vTwinkle;

  void main() {
    vec3 p = position;
    float t = uTime;

    // Layered sine waves for a slow, rolling "data sea"
    float h = sin(p.x * 0.22 + t * 0.6) * 0.9
            + sin(p.z * 0.28 + t * 0.45) * 0.7
            + sin((p.x + p.z) * 0.12 + t * 0.8) * 0.6;
    // A ripple that pulses outward from the center
    float d = length(p.xz);
    h += sin(d * 0.6 - t * 1.6) * 0.35 * exp(-d * 0.04);

    // Cursor: raise a glowing mound and push points slightly outward
    vec2 dir = p.xz - uMouse;
    float dm = length(dir);
    float infl = exp(-dm * dm * 0.05) * uStrength;
    h += infl * 1.2;
    if (dm > 0.001) p.xz += dir / dm * exp(-dm * dm * 0.08) * uStrength * 0.5;
    vGlow = infl;

    // Ripples left by cursor movement
    vRing = 0.0;
    for (int i = 0; i < ${RIPPLES}; i++) {
      vec4 r = uRipples[i];
      float age = t - r.z;
      if (age < 0.0 || age > ${RIPPLE_LIFE.toFixed(1)}) continue;
      float front = distance(position.xz, r.xy) - age * ${RIPPLE_SPEED.toFixed(1)};
      float ring = exp(-front * front * 0.35) * (1.0 - age / ${RIPPLE_LIFE.toFixed(1)});
      h += ring * r.w;
      vRing += ring * min(r.w, 1.5);
    }

    // A scanning beam that sweeps toward the viewer
    float scanZ = mod(t * 5.0, 90.0) - 60.0;
    vScan = exp(-pow(position.z - scanZ, 2.0) * 0.15);
    h += vScan * 0.2;

    p.y += h;

    // Per-point twinkle
    float n = fract(sin(dot(position.xz, vec2(12.9898, 78.233))) * 43758.5453);
    vTwinkle = 0.92 + 0.08 * sin(t * 2.0 + n * 6.2831);

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float size = max(2.6 + h * 0.5 + vGlow * 1.0 + vRing * 0.8, 0.5);
    gl_PointSize = min(size * (24.0 / -mv.z), 7.0) * uPixelRatio;

    vHeight = h;
    vDepth = -mv.z;
  }
`;

const waveFragment = /* glsl */ `
  uniform vec3 uColor;
  uniform vec3 uDeep;
  varying float vHeight;
  varying float vDepth;
  varying float vGlow;
  varying float vRing;
  varying float vScan;
  varying float vTwinkle;

  void main() {
    // Soft round points
    float r = length(gl_PointCoord - 0.5);
    if (r > 0.5) discard;
    float soft = smoothstep(0.5, 0.0, r);

    // Crests glow brighter green, troughs sink into a deep teal
    float k = clamp((vHeight + 2.0) / 4.0, 0.0, 1.0);
    vec3 color = mix(uDeep, uColor, k);
    color = mix(color, uColor, vGlow * 0.4);
    color += uColor * (vRing * 0.25 + vScan * 0.15);

    // Fade with distance so the field dissolves into the page
    float fog = smoothstep(70.0, 12.0, vDepth);
    float alpha = (0.25 + k * 0.45 + vGlow * 0.3 + vRing * 0.35 + vScan * 0.2) * 0.9;
    gl_FragColor = vec4(color, soft * fog * alpha * vTwinkle);
  }
`;

const dustVertex = /* glsl */ `
  uniform float uTime;
  uniform float uPixelRatio;
  uniform vec3 uCursor;
  uniform float uStrength;
  attribute float aSeed;
  varying float vAlpha;

  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    // Specks near the cursor brighten slightly
    float near = exp(-pow(distance(position, uCursor), 2.0) * 0.03) * uStrength;
    gl_PointSize = (3.0 + aSeed * 4.0 + near * 1.5) * uPixelRatio * (20.0 / -mv.z);
    vAlpha = 0.15 + 0.3 * abs(sin(uTime * (0.5 + aSeed) + aSeed * 10.0)) + near * 0.25;
  }
`;

const dustFragment = /* glsl */ `
  uniform vec3 uColor;
  varying float vAlpha;

  void main() {
    float r = length(gl_PointCoord - 0.5);
    if (r > 0.5) discard;
    float glow = pow(smoothstep(0.5, 0.0, r), 2.0);
    gl_FragColor = vec4(uColor, glow * vAlpha);
  }
`;

const lineVertex = /* glsl */ `
  attribute float aAlpha;
  varying float vAlpha;

  void main() {
    vAlpha = aAlpha;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const lineFragment = /* glsl */ `
  uniform vec3 uColor;
  varying float vAlpha;

  void main() {
    gl_FragColor = vec4(uColor, vAlpha);
  }
`;

export default function Background() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pixelRatio = Math.min(window.devicePixelRatio, 1.25);

    const renderer = new THREE.WebGLRenderer({
      antialias: false,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 200);
    camera.position.set(0, 7, 24);
    camera.lookAt(0, 0, -10);

    const green = themeColor("--color-success", "oklch(76% 0.177 163.223)");
    const deep = new THREE.Vector3(0.02, 0.25, 0.22);

    // Wave field: a grid of points on the XZ plane
    const cols = 130;
    const rows = 105;
    const spacing = 0.7;
    const wavePositions = new Float32Array(cols * rows * 3);
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        const idx = (i * rows + j) * 3;
        wavePositions[idx] = (i - cols / 2) * spacing;
        wavePositions[idx + 1] = 0;
        wavePositions[idx + 2] = (j - rows / 2) * spacing - 5;
      }
    }
    const ripples = Array.from({ length: RIPPLES }, () => new THREE.Vector4(0, 0, -100, 0));
    const waveGeometry = new THREE.BufferGeometry();
    waveGeometry.setAttribute("position", new THREE.BufferAttribute(wavePositions, 3));
    const waveMaterial = new THREE.ShaderMaterial({
      vertexShader: waveVertex,
      fragmentShader: waveFragment,
      uniforms: {
        uTime: { value: 0 },
        uPixelRatio: { value: pixelRatio },
        uColor: { value: green },
        uDeep: { value: deep },
        uMouse: { value: new THREE.Vector2(0, 0) },
        uStrength: { value: 0 },
        uRipples: { value: ripples },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    scene.add(new THREE.Points(waveGeometry, waveMaterial));

    // Floating dust motes, animated on the CPU so lines can connect to them
    const dustCount = 160;
    const dustBase = new Float32Array(dustCount * 3);
    const dustSeeds = new Float32Array(dustCount);
    for (let i = 0; i < dustCount; i++) {
      dustBase[i * 3] = (Math.random() - 0.5) * 70;
      dustBase[i * 3 + 1] = Math.random() * 20;
      dustBase[i * 3 + 2] = (Math.random() - 0.5) * 50 - 8;
      dustSeeds[i] = Math.random();
    }
    const dustPositions = new Float32Array(dustCount * 3);
    const dustGeometry = new THREE.BufferGeometry();
    const dustAttr = new THREE.BufferAttribute(dustPositions, 3);
    dustAttr.setUsage(THREE.DynamicDrawUsage);
    dustGeometry.setAttribute("position", dustAttr);
    dustGeometry.setAttribute("aSeed", new THREE.BufferAttribute(dustSeeds, 1));
    const dustMaterial = new THREE.ShaderMaterial({
      vertexShader: dustVertex,
      fragmentShader: dustFragment,
      uniforms: {
        uTime: { value: 0 },
        uPixelRatio: { value: pixelRatio },
        uColor: { value: green },
        uCursor: { value: new THREE.Vector3(0, -100, 0) },
        uStrength: { value: 0 },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const dust = new THREE.Points(dustGeometry, dustMaterial);
    dust.frustumCulled = false;
    scene.add(dust);

    // Faint "neural" lines between dust motes near the cursor
    const maxSegments = 160;
    const linePositions = new Float32Array(maxSegments * 6);
    const lineAlphas = new Float32Array(maxSegments * 2);
    const lineGeometry = new THREE.BufferGeometry();
    const linePosAttr = new THREE.BufferAttribute(linePositions, 3);
    const lineAlphaAttr = new THREE.BufferAttribute(lineAlphas, 1);
    linePosAttr.setUsage(THREE.DynamicDrawUsage);
    lineAlphaAttr.setUsage(THREE.DynamicDrawUsage);
    lineGeometry.setAttribute("position", linePosAttr);
    lineGeometry.setAttribute("aAlpha", lineAlphaAttr);
    const lineMaterial = new THREE.ShaderMaterial({
      vertexShader: lineVertex,
      fragmentShader: lineFragment,
      uniforms: { uColor: { value: green } },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const lines = new THREE.LineSegments(lineGeometry, lineMaterial);
    lines.frustumCulled = false;
    scene.add(lines);

    // Point hovering over the waves under the cursor (invisible; dust reacts to it)
    const cursor = new THREE.Vector3(0, -100, 0);

    // Pointer tracking: screen position, projected onto the wave plane
    const pointer = new THREE.Vector2(0, 0);
    const raycaster = new THREE.Raycaster();
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const hit = new THREE.Vector3();
    const mouseTarget = new THREE.Vector2(0, 0);
    const mouseWorld = new THREE.Vector2(0, 0);
    let strength = 0;
    let lastMove = -10;
    let lastRipple = -10;
    const lastRipplePos = new THREE.Vector2(1e3, 1e3);
    let rippleIndex = 0;

    const start = performance.now();
    const now = () => (performance.now() - start) / 1000;

    const addRipple = (x: number, z: number, amplitude: number) => {
      ripples[rippleIndex].set(x, z, now(), amplitude);
      rippleIndex = (rippleIndex + 1) % RIPPLES;
    };

    const onPointerMove = (e: PointerEvent) => {
      pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
      lastMove = now();
    };
    const onPointerLeave = () => {
      lastMove = -10;
    };
    // Offset the camera's view by the page scroll so the scene moves up with the content,
    // and fade it out over the first screen of scrolling
    let opacity = -1;
    const followScroll = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      camera.setViewOffset(w, h, 0, window.scrollY, w, h);
      const fade = Math.round(Math.min(Math.max(1 - window.scrollY / (h * 0.8), 0), 1) * 100) / 100;
      if (fade !== opacity) {
        opacity = fade;
        renderer.domElement.style.opacity = String(fade);
      }
      return fade > 0;
    };
    const onScroll = () => {
      followScroll();
      renderer.render(scene, camera);
    };

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      if (reduceMotion) onScroll();
    };
    window.addEventListener("resize", onResize);
    if (reduceMotion) {
      window.addEventListener("scroll", onScroll, { passive: true });
    } else {
      window.addEventListener("pointermove", onPointerMove);
      document.documentElement.addEventListener("pointerleave", onPointerLeave);
    }

    const updateDust = (t: number) => {
      for (let i = 0; i < dustCount; i++) {
        const s = dustSeeds[i];
        dustPositions[i * 3] = dustBase[i * 3] + Math.sin(t * 0.3 + s * 6.28) * 0.8;
        dustPositions[i * 3 + 1] = ((dustBase[i * 3 + 1] + t * (0.3 + s * 0.5)) % 20) - 4;
        dustPositions[i * 3 + 2] = dustBase[i * 3 + 2];
      }
      dustAttr.needsUpdate = true;
    };

    const near: number[] = [];
    const updateLines = () => {
      let seg = 0;
      const push = (
        ax: number, ay: number, az: number,
        bx: number, by: number, bz: number,
        alpha: number,
      ) => {
        if (seg >= maxSegments) return;
        linePositions.set([ax, ay, az, bx, by, bz], seg * 6);
        lineAlphas[seg * 2] = alpha;
        lineAlphas[seg * 2 + 1] = alpha;
        seg++;
      };

      near.length = 0;
      if (strength > 0.01) {
        const radius = 10;
        for (let i = 0; i < dustCount; i++) {
          const d = Math.hypot(
            dustPositions[i * 3] - cursor.x,
            dustPositions[i * 3 + 1] - cursor.y,
            dustPositions[i * 3 + 2] - cursor.z,
          );
          if (d < radius) near.push(i);
        }
        for (let a = 0; a < near.length; a++) {
          for (let b = a + 1; b < near.length; b++) {
            const i = near[a] * 3;
            const j = near[b] * 3;
            const d = Math.hypot(
              dustPositions[i] - dustPositions[j],
              dustPositions[i + 1] - dustPositions[j + 1],
              dustPositions[i + 2] - dustPositions[j + 2],
            );
            if (d < 5) {
              push(
                dustPositions[i], dustPositions[i + 1], dustPositions[i + 2],
                dustPositions[j], dustPositions[j + 1], dustPositions[j + 2],
                (1 - d / 5) * 0.15 * strength,
              );
            }
          }
        }
      }
      lineGeometry.setDrawRange(0, seg * 2);
      linePosAttr.needsUpdate = true;
      lineAlphaAttr.needsUpdate = true;
    };

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      if (!followScroll()) return;
      const t = now();

      // Gentle camera parallax
      camera.position.x += (pointer.x * 3 - camera.position.x) * 0.03;
      camera.position.y += (7 + pointer.y * 1.5 - camera.position.y) * 0.03;
      camera.lookAt(0, 0, -10);

      // Where the cursor lands on the wave plane
      raycaster.setFromCamera(pointer, camera);
      if (raycaster.ray.intersectPlane(plane, hit)) {
        mouseTarget.set(hit.x, THREE.MathUtils.clamp(hit.z, -40, 30));
      }
      mouseWorld.lerp(mouseTarget, 0.12);

      // Fade the interaction in while the cursor is active, out when idle
      const active = t - lastMove < 2.5 ? 1 : 0;
      strength += (active - strength) * 0.05;

      // Leave a trail of small ripples while moving
      if (
        active &&
        t - lastRipple > 0.12 &&
        mouseWorld.distanceTo(lastRipplePos) > 1.5
      ) {
        addRipple(mouseWorld.x, mouseWorld.y, 0.3);
        lastRipple = t;
        lastRipplePos.copy(mouseWorld);
      }

      const surface = waveHeight(mouseWorld.x, mouseWorld.y, t) + 1.2 * strength;
      cursor.set(mouseWorld.x, surface + 1.4, mouseWorld.y);

      waveMaterial.uniforms.uTime.value = t;
      waveMaterial.uniforms.uMouse.value.copy(mouseWorld);
      waveMaterial.uniforms.uStrength.value = strength;
      dustMaterial.uniforms.uTime.value = t;
      dustMaterial.uniforms.uCursor.value.copy(cursor);
      dustMaterial.uniforms.uStrength.value = strength;

      updateDust(t);
      updateLines();

      renderer.render(scene, camera);
    };

    if (reduceMotion) {
      waveMaterial.uniforms.uTime.value = 4;
      dustMaterial.uniforms.uTime.value = 4;
      updateDust(4);
      onScroll();
    } else {
      animate();
    }

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("pointermove", onPointerMove);
      document.documentElement.removeEventListener("pointerleave", onPointerLeave);
      waveGeometry.dispose();
      waveMaterial.dispose();
      dustGeometry.dispose();
      dustMaterial.dispose();
      lineGeometry.dispose();
      lineMaterial.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10"
    />
  );
}
