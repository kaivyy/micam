/**
 * FsrUpscaler - 2-Pass AMD FidelityFX Super Resolution (FSR 1.0) for WebGL
 *
 * Implements 2-pass super-resolution and contrast-adaptive edge sharpening:
 * - Pass 1: EASU (Edge-Adaptive Spatial Upsampling) - directional 12-tap Lanczos
 * - Pass 2: RCAS (Robust Contrast-Adaptive Sharpening) - ringing-free texture recovery
 */
(function (global) {
  'use strict';

  const VS_SOURCE = `
    attribute vec2 aPosition;
    varying vec2 vUv;
    void main() {
      vUv = (aPosition + 1.0) * 0.5;
      gl_Position = vec4(aPosition, 0.0, 1.0);
    }
  `;

  const EASU_FS_SOURCE = `
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D uSourceTexture;
    uniform vec2 uSourceSize;
    uniform vec2 uOutputSize;
    uniform vec2 uCropMin;
    uniform vec2 uCropMax;

    vec3 sampleSource(vec2 p) {
      vec2 uv = clamp((p + 0.5) / uSourceSize, 0.0, 1.0);
      return texture2D(uSourceTexture, uv).rgb;
    }

    void FsrEasuTapF(
      inout vec3 aC,
      inout float aW,
      vec2 off,
      vec2 dir,
      vec2 len,
      float lob,
      float clp,
      vec3 c
    ) {
      vec2 v = vec2(dot(off, dir), dot(off, vec2(-dir.y, dir.x))) * len;
      float d2 = min(dot(v, v), clp);
      float wB = 0.4 * d2 - 1.0;
      float wA = lob * d2 - 1.0;
      wB *= wB;
      wA *= wA;
      wB = 1.5625 * wB - 0.5625;
      float w = wB * wA;
      aC += c * w;
      aW += w;
    }

    void FsrEasuSetF(
      inout vec2 dir,
      inout float len,
      float w,
      float lA, float lB, float lC, float lD, float lE
    ) {
      float lenX = max(abs(lD - lC), abs(lC - lB));
      float dirX = lD - lB;
      dir.x += dirX * w;
      lenX = clamp(abs(dirX) / max(lenX, 0.0001), 0.0, 1.0);
      len += lenX * lenX * w;

      float lenY = max(abs(lE - lC), abs(lC - lA));
      float dirY = lE - lA;
      dir.y += dirY * w;
      lenY = clamp(abs(dirY) / max(lenY, 0.0001), 0.0, 1.0);
      len += lenY * lenY * w;
    }

    void main() {
      vec2 cropSpan = uCropMax - uCropMin;
      vec2 inputViewport = cropSpan * uSourceSize;
      // Invert Y coordinate so top of canvas samples row 0 (top of HTML video)
      vec2 fragCoord = vec2(gl_FragCoord.x, uOutputSize.y - gl_FragCoord.y);
      vec2 pp = fragCoord * (inputViewport / uOutputSize) + (uCropMin * uSourceSize);
      vec2 fp = floor(pp);
      pp -= fp;

      vec2 p0 = fp;
      vec2 p1 = p0 + vec2(-1.0, 1.0);
      vec2 p2 = p0 + vec2(1.0, 1.0);
      vec2 p3 = p0 + vec2(0.0, 2.0);

      vec3 bC = sampleSource(p0 + vec2(0.0, -1.0)); float bL = bC.g + 0.5 * (bC.r + bC.b);
      vec3 cC = sampleSource(p0 + vec2(1.0, -1.0)); float cL = cC.g + 0.5 * (cC.r + cC.b);
      vec3 iC = sampleSource(p1 + vec2(0.0, 0.0));  float iL = iC.g + 0.5 * (iC.r + iC.b);
      vec3 jC = sampleSource(p1 + vec2(1.0, 0.0));  float jL = jC.g + 0.5 * (jC.r + jC.b);
      vec3 fC = sampleSource(p0 + vec2(0.0, 0.0));  float fL = fC.g + 0.5 * (fC.r + fC.b);
      vec3 eC = sampleSource(p0 + vec2(-1.0, 0.0)); float eL = eC.g + 0.5 * (eC.r + eC.b);
      vec3 kC = sampleSource(p2 + vec2(0.0, 0.0));  float kL = kC.g + 0.5 * (kC.r + kC.b);
      vec3 lC = sampleSource(p2 + vec2(1.0, 0.0));  float lL = lC.g + 0.5 * (lC.r + lC.b);
      vec3 hC = sampleSource(p0 + vec2(2.0, 0.0));  float hL = hC.g + 0.5 * (hC.r + hC.b);
      vec3 gC = sampleSource(p0 + vec2(1.0, 0.0));  float gL = gC.g + 0.5 * (gC.r + gC.b);
      vec3 oC = sampleSource(p3 + vec2(1.0, 0.0));  float oL = oC.g + 0.5 * (oC.r + oC.b);
      vec3 nC = sampleSource(p3 + vec2(0.0, 0.0));  float nL = nC.g + 0.5 * (nC.r + nC.b);

      vec2 dir = vec2(0.0);
      float len = 0.0;
      FsrEasuSetF(dir, len, (1.0 - pp.x) * (1.0 - pp.y), bL, eL, fL, gL, jL);
      FsrEasuSetF(dir, len, pp.x * (1.0 - pp.y),         cL, fL, gL, hL, kL);
      FsrEasuSetF(dir, len, (1.0 - pp.x) * pp.y,         fL, iL, jL, kL, nL);
      FsrEasuSetF(dir, len, pp.x * pp.y,                 gL, jL, kL, lL, oL);

      vec2 dir2 = dir * dir;
      float dirR = dir2.x + dir2.y;
      if (dirR < (1.0 / 32768.0)) {
        vec4 w = vec4((1.0 - pp.x) * (1.0 - pp.y), pp.x * (1.0 - pp.y), (1.0 - pp.x) * pp.y, pp.x * pp.y);
        vec3 pix = clamp(fC * w.x + gC * w.y + jC * w.z + kC * w.w, 0.0, 1.0);
        gl_FragColor = vec4(pix, 1.0);
        return;
      }
      dirR = inversesqrt(dirR);
      dir *= dirR;

      len = len * 0.5;
      len *= len;
      float stretch = dot(dir, dir) / max(max(abs(dir.x), abs(dir.y)), 0.0001);
      vec2 len2 = vec2(1.0 + (stretch - 1.0) * len, 1.0 - 0.5 * len);
      float lob = 0.5 - 0.29 * len;
      float clp = 1.0 / max(lob, 0.0001);

      vec3 min4 = min(min(fC, gC), min(jC, kC));
      vec3 max4 = max(max(fC, gC), max(jC, kC));

      vec3 aC = vec3(0.0);
      float aW = 0.0;
      FsrEasuTapF(aC, aW, vec2( 0.0, -1.0) - pp, dir, len2, lob, clp, bC);
      FsrEasuTapF(aC, aW, vec2( 1.0, -1.0) - pp, dir, len2, lob, clp, cC);
      FsrEasuTapF(aC, aW, vec2(-1.0,  1.0) - pp, dir, len2, lob, clp, iC);
      FsrEasuTapF(aC, aW, vec2( 0.0,  1.0) - pp, dir, len2, lob, clp, jC);
      FsrEasuTapF(aC, aW, vec2( 0.0,  0.0) - pp, dir, len2, lob, clp, fC);
      FsrEasuTapF(aC, aW, vec2(-1.0,  0.0) - pp, dir, len2, lob, clp, eC);
      FsrEasuTapF(aC, aW, vec2( 1.0,  1.0) - pp, dir, len2, lob, clp, kC);
      FsrEasuTapF(aC, aW, vec2( 2.0,  1.0) - pp, dir, len2, lob, clp, lC);
      FsrEasuTapF(aC, aW, vec2( 2.0,  0.0) - pp, dir, len2, lob, clp, hC);
      FsrEasuTapF(aC, aW, vec2( 1.0,  0.0) - pp, dir, len2, lob, clp, gC);
      FsrEasuTapF(aC, aW, vec2( 1.0,  2.0) - pp, dir, len2, lob, clp, oC);
      FsrEasuTapF(aC, aW, vec2( 0.0,  2.0) - pp, dir, len2, lob, clp, nC);

      vec3 pix = aC / max(aW, 0.0001);
      pix = min(max4, max(min4, pix));
      gl_FragColor = vec4(clamp(pix, 0.0, 1.0), 1.0);
    }
  `;

  const RCAS_FS_SOURCE = `
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D uEasuTexture;
    uniform vec2 uResolution;
    uniform float uSharpness;

    void main() {
      vec2 sp = gl_FragCoord.xy;
      vec3 b = texture2D(uEasuTexture, (sp + vec2( 0.0, -1.0)) / uResolution).rgb;
      vec3 d = texture2D(uEasuTexture, (sp + vec2(-1.0,  0.0)) / uResolution).rgb;
      vec3 e = texture2D(uEasuTexture, sp / uResolution).rgb;
      vec3 f = texture2D(uEasuTexture, (sp + vec2( 1.0,  0.0)) / uResolution).rgb;
      vec3 h = texture2D(uEasuTexture, (sp + vec2( 0.0,  1.0)) / uResolution).rgb;

      float bL = b.g + 0.5 * (b.b + b.r);
      float dL = d.g + 0.5 * (d.b + d.r);
      float eL = e.g + 0.5 * (e.b + e.r);
      float fL = f.g + 0.5 * (f.b + f.r);
      float hL = h.g + 0.5 * (h.b + h.r);

      float nz = 0.25 * (bL + dL + fL + hL) - eL;
      float range = max(max(bL, dL), max(eL, max(fL, hL))) - min(min(bL, dL), min(eL, min(fL, hL)));
      nz = clamp(abs(nz) / max(range, 0.0001), 0.0, 1.0);
      nz = 1.0 - 0.5 * nz;

      vec3 mn4 = min(b, min(f, h));
      vec3 mx4 = max(b, max(f, h));
      vec2 peakC = vec2(1.0, -4.0);
      vec3 hitMin = mn4 / (4.0 * max(mx4, vec3(0.0001)));
      vec3 hitMax = (peakC.x - mx4) / (4.0 * mn4 + peakC.y);
      vec3 lobeRGB = max(-hitMin, hitMax);

      float con = exp2(-uSharpness);
      float FSR_RCAS_LIMIT = 0.1875;
      float lobe = max(-FSR_RCAS_LIMIT, min(max(lobeRGB.r, max(lobeRGB.g, lobeRGB.b)), 0.0)) * con;
      lobe *= nz;

      vec3 resolved = (lobe * (b + d + h + f) + e) / (4.0 * lobe + 1.0);
      gl_FragColor = vec4(clamp(resolved, 0.0, 1.0), 1.0);
    }
  `;

  function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const info = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(`Shader compilation error: ${info}`);
    }
    return shader;
  }

  function createProgram(gl, vsSource, fsSource) {
    const vs = createShader(gl, gl.VERTEX_SHADER, vsSource);
    const fs = createShader(gl, gl.FRAGMENT_SHADER, fsSource);
    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      const info = gl.getProgramInfoLog(program);
      gl.deleteProgram(program);
      throw new Error(`Program link error: ${info}`);
    }
    return program;
  }

  class FsrUpscaler {
    constructor(videoEl, canvasEl, options = {}) {
      this.video = videoEl;
      this.canvas = canvasEl;
      this.sharpness = options.sharpness !== undefined ? options.sharpness : 0.2; // 0.0 (sharpest) to 1.5
      this.gl = null;
      this.running = false;
      this.hasRenderedFirstFrame = false;
      this.onFirstFrame = options.onFirstFrame || null;
      this.rafId = null;
      this.vfcId = null;

      // Normalized crop window [0..1]
      this.cropMin = [0.0, 0.0];
      this.cropMax = [1.0, 1.0];

      // WebGL Resources
      this.quadBuffer = null;
      this.easuProgram = null;
      this.rcasProgram = null;
      this.sourceTexture = null;
      this.fbo = null;
      this.fboTexture = null;
      this.fboWidth = 0;
      this.fboHeight = 0;

      // Uniform Locations
      this.easuLocs = {};
      this.rcasLocs = {};

      this._boundOnFrame = this._onFrame.bind(this);
      this._boundContextLost = this._onContextLost.bind(this);
      this._boundContextRestored = this._onContextRestored.bind(this);
    }

    init() {
      try {
        const glOpts = {
          alpha: false,
          depth: false,
          stencil: false,
          antialias: false,
          preserveDrawingBuffer: true,
          powerPreference: 'high-performance'
        };

        this.gl = this.canvas.getContext('webgl2', glOpts) ||
                  this.canvas.getContext('webgl', glOpts) ||
                  this.canvas.getContext('experimental-webgl', glOpts);

        if (!this.gl) {
          console.warn('[FsrUpscaler] WebGL context not available');
          return false;
        }

        const gl = this.gl;
        this.canvas.addEventListener('webglcontextlost', this._boundContextLost, false);
        this.canvas.addEventListener('webglcontextrestored', this._boundContextRestored, false);

        // Quad geometry covering NDC [-1, 1]
        const positions = new Float32Array([
          -1.0, -1.0,
           1.0, -1.0,
          -1.0,  1.0,
          -1.0,  1.0,
           1.0, -1.0,
           1.0,  1.0
        ]);
        this.quadBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

        // Compile Pass 1 (EASU) Program
        this.easuProgram = createProgram(gl, VS_SOURCE, EASU_FS_SOURCE);
        this.easuLocs = {
          aPosition: gl.getAttribLocation(this.easuProgram, 'aPosition'),
          uSourceTexture: gl.getUniformLocation(this.easuProgram, 'uSourceTexture'),
          uSourceSize: gl.getUniformLocation(this.easuProgram, 'uSourceSize'),
          uOutputSize: gl.getUniformLocation(this.easuProgram, 'uOutputSize'),
          uCropMin: gl.getUniformLocation(this.easuProgram, 'uCropMin'),
          uCropMax: gl.getUniformLocation(this.easuProgram, 'uCropMax')
        };

        // Compile Pass 2 (RCAS) Program
        this.rcasProgram = createProgram(gl, VS_SOURCE, RCAS_FS_SOURCE);
        this.rcasLocs = {
          aPosition: gl.getAttribLocation(this.rcasProgram, 'aPosition'),
          uEasuTexture: gl.getUniformLocation(this.rcasProgram, 'uEasuTexture'),
          uResolution: gl.getUniformLocation(this.rcasProgram, 'uResolution'),
          uSharpness: gl.getUniformLocation(this.rcasProgram, 'uSharpness')
        };

        // Source Video Texture
        this.sourceTexture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, this.sourceTexture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

        // Placeholder 1x1 black pixel until video frame arrives
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]));

        // Framebuffer Object (FBO) for EASU output
        this.fbo = gl.createFramebuffer();
        this.fboTexture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, this.fboTexture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

        return true;
      } catch (err) {
        console.error('[FsrUpscaler] Initialization failed:', err);
        return false;
      }
    }

    _onContextLost(e) {
      e.preventDefault();
      this.stop();
      console.warn('[FsrUpscaler] WebGL context lost');
    }

    _onContextRestored() {
      console.info('[FsrUpscaler] WebGL context restored, re-initializing...');
      if (this.init()) {
        this.start();
      }
    }

    setCrop(scale, x, y, containerWidth, containerHeight) {
      if (!scale || scale <= 1.0) {
        this.cropMin = [0.0, 0.0];
        this.cropMax = [1.0, 1.0];
        return;
      }
      const span = 1.0 / scale;
      const cW = Math.max(containerWidth || 1, 1);
      const cH = Math.max(containerHeight || 1, 1);

      // Map container pixel pan (x, y) to UV center offset.
      // In DOM video space, UV coordinate 0.0 is the top of the video, 1.0 is the bottom.
      // Dragging down (positive y) brings the top into view, so uvCenterY decreases towards 0.0.
      const uvCenterX = 0.5 - (x / (cW * scale));
      const uvCenterY = 0.5 - (y / (cH * scale));

      const uMin = Math.max(0.0, Math.min(1.0 - span, uvCenterX - span * 0.5));
      const uMax = Math.min(1.0, uMin + span);
      const vMin = Math.max(0.0, Math.min(1.0 - span, uvCenterY - span * 0.5));
      const vMax = Math.min(1.0, vMin + span);

      this.cropMin = [uMin, vMin];
      this.cropMax = [uMax, vMax];
    }

    setSharpness(stops) {
      // 0.0 is maximum sharpness, 0.2 default, 1.0 is soft
      this.sharpness = Math.max(0.0, Math.min(2.0, stops));
    }

    _ensureCanvasSize() {
      const gl = this.gl;
      if (!gl) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2.0);
      const displayWidth = Math.floor((this.canvas.clientWidth || this.canvas.parentElement?.clientWidth || 640) * dpr);
      const displayHeight = Math.floor((this.canvas.clientHeight || this.canvas.parentElement?.clientHeight || 360) * dpr);

      if (this.canvas.width !== displayWidth || this.canvas.height !== displayHeight) {
        this.canvas.width = Math.max(16, displayWidth);
        this.canvas.height = Math.max(16, displayHeight);
      }

      if (this.fboWidth !== this.canvas.width || this.fboHeight !== this.canvas.height) {
        this.fboWidth = this.canvas.width;
        this.fboHeight = this.canvas.height;

        gl.bindTexture(gl.TEXTURE_2D, this.fboTexture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, this.fboWidth, this.fboHeight, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);

        gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.fboTexture, 0);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      }
    }

    render() {
      const gl = this.gl;
      if (!gl || !this.video) return;

      // Verify video element has valid frames
      if (this.video.readyState < 2 || !this.video.videoWidth || !this.video.videoHeight) {
        return;
      }

      this._ensureCanvasSize();
      const outW = this.canvas.width;
      const outH = this.canvas.height;
      if (outW <= 0 || outH <= 0) return;

      // 1. Upload new frame to sourceTexture
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.sourceTexture);
      try {
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.video);
      } catch (e) {
        return;
      }

      // 2. Setup vertex buffer
      gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuffer);

      // --- PASS 1: EASU (Edge-Adaptive Spatial Upsampling) -> FBO ---
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
      gl.viewport(0, 0, this.fboWidth, this.fboHeight);
      gl.useProgram(this.easuProgram);

      gl.enableVertexAttribArray(this.easuLocs.aPosition);
      gl.vertexAttribPointer(this.easuLocs.aPosition, 2, gl.FLOAT, false, 0, 0);

      gl.uniform1i(this.easuLocs.uSourceTexture, 0);
      gl.uniform2f(this.easuLocs.uSourceSize, this.video.videoWidth, this.video.videoHeight);
      gl.uniform2f(this.easuLocs.uOutputSize, this.fboWidth, this.fboHeight);
      gl.uniform2f(this.easuLocs.uCropMin, this.cropMin[0], this.cropMin[1]);
      gl.uniform2f(this.easuLocs.uCropMax, this.cropMax[0], this.cropMax[1]);

      gl.drawArrays(gl.TRIANGLES, 0, 6);

      // --- PASS 2: RCAS (Robust Contrast-Adaptive Sharpening) -> Screen ---
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, outW, outH);
      gl.useProgram(this.rcasProgram);

      gl.enableVertexAttribArray(this.rcasLocs.aPosition);
      gl.vertexAttribPointer(this.rcasLocs.aPosition, 2, gl.FLOAT, false, 0, 0);

      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, this.fboTexture);
      gl.uniform1i(this.rcasLocs.uEasuTexture, 1);
      gl.uniform2f(this.rcasLocs.uResolution, outW, outH);
      gl.uniform1f(this.rcasLocs.uSharpness, this.sharpness);

      gl.drawArrays(gl.TRIANGLES, 0, 6);

      if (!this.hasRenderedFirstFrame) {
        this.hasRenderedFirstFrame = true;
        if (typeof this.onFirstFrame === 'function') {
          this.onFirstFrame();
        }
      }
    }

    _onFrame() {
      if (!this.running) return;
      this.render();
      this._scheduleNext();
    }

    _scheduleNext() {
      if (!this.running) return;
      if (this.video && 'requestVideoFrameCallback' in this.video) {
        this.vfcId = this.video.requestVideoFrameCallback(this._boundOnFrame);
      } else {
        this.rafId = requestAnimationFrame(this._boundOnFrame);
      }
    }

    start() {
      if (this.running) return;
      this.running = true;
      this._scheduleNext();
    }

    stop() {
      this.running = false;
      if (this.rafId) {
        cancelAnimationFrame(this.rafId);
        this.rafId = null;
      }
      if (this.vfcId && this.video && 'cancelVideoFrameCallback' in this.video) {
        this.video.cancelVideoFrameCallback(this.vfcId);
        this.vfcId = null;
      }
    }

    captureSnapshot(format = 'image/jpeg', quality = 0.95) {
      return new Promise((resolve, reject) => {
        try {
          this.render();
          this.canvas.toBlob((blob) => {
            if (blob) resolve(blob);
            else reject(new Error('Canvas toBlob returned null'));
          }, format, quality);
        } catch (err) {
          reject(err);
        }
      });
    }

    destroy() {
      this.stop();
      const gl = this.gl;
      if (!gl) return;

      this.canvas.removeEventListener('webglcontextlost', this._boundContextLost);
      this.canvas.removeEventListener('webglcontextrestored', this._boundContextRestored);

      if (this.quadBuffer) gl.deleteBuffer(this.quadBuffer);
      if (this.easuProgram) gl.deleteProgram(this.easuProgram);
      if (this.rcasProgram) gl.deleteProgram(this.rcasProgram);
      if (this.sourceTexture) gl.deleteTexture(this.sourceTexture);
      if (this.fboTexture) gl.deleteTexture(this.fboTexture);
      if (this.fbo) gl.deleteFramebuffer(this.fbo);

      this.gl = null;
    }
  }

  global.FsrUpscaler = FsrUpscaler;
})(typeof window !== 'undefined' ? window : this);
