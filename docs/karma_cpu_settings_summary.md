# Karma CPU Refined Settings — rubber_toy scene
## Applied to: /stage/rendersettings1

### Material Context
- Material: rubber_toy_mat (MTLXStandard Surface)
- Roughness: 0.72 (diffuse-dominant, no glass/transmission)
- Base color: warm red [0.9, 0.18, 0.08]
- No metalness, no transmission — pure diffuse + soft specular

### Karma CPU Settings Applied

| Setting | Before | After | Reasoning |
|---|---|---|---|
| Image Mode | Progressive | **Bucket** | CPU production: bucket is more efficient multi-core |
| Bucket Size | 32 | **64** | Better CPU core utilization |
| Bucket Order | Middle | **Middle** | Hero object center-frame, renders outward |
| Pixel Samples | 9 | **256** | Production-grade CPU quality |
| Path Traced Samples | 128 | **512** | Rubber at 0.72 roughness needs solid indirect |
| Russian Roulette Cutoff | 2 | **3** | Deeper GI paths for diffuse rubber |
| Light Sampling | Light Tree | **Light Tree** | 2 lights (area + dome): tree efficient |
| Light Sampling Quality | 1.0 | **1.5** | Area light falloff needs extra samples |
| Screendoor Limit | 4 | **2** | Tighter alpha for matte rubber edges |
| Indirect Guiding | OFF | **ON** | Rubber 0.72 diffuse = ideal for path guiding |
| Guiding Training Samples | 0 | **128** | Pre-pass for diffuse + SSS components |
| Guiding Components | — | **diffuse + sss** | Matches rubber shader lobes |
| Color Limit | 20 | **10** | Rough rubber won't spike; tighter = less noise |
| Pixel Filter | gauss 2.0 | **blackman-harris 1.5** | Sharper on anamorphic 2.39:1 frame |
| Pixel Oracle | variance | **variance** | Keep variance AA |
| Auto Headlight | ON | **OFF** | Real lights present, no fallback needed |
| Diffuse Quality (geo) | 1.0 | **1.5** | Rubber is diffuse-dominant |
| Reflect Quality (geo) | 1.0 | **1.0** | Moderate glossy (0.28 specular weight) |
| Refract Quality (geo) | 1.0 | **0.5** | No glass — save samples |
| Diffuse Limit | 1.0 | **3.0** | 3 GI bounces for realistic rubber |
| Reflect Limit | 4.0 | **2.0** | Rubber doesn't need deep reflections |
| Refract Limit | 4.0 | **0.0** | No refraction needed |
| Fix Shadow Terminator | ON | **ON** | Essential for low-poly toy mesh |
| Variance AA Threshold | 0.01 | **0.005** | Tighter = cleaner CPU production |
| Min Secondary Samples | 1 | **4** | More reliable convergence |
| Max Secondary Samples | 9 | **16** | Headroom for rough diffuse regions |
| Cache Ratio | 0.25 | **0.35** | CPU benefits from larger texture cache |
| Camera | /cameras/camera1 | **/cameras/phantom_anamorphic_cam1** | Correct camera |
| DOF | enabled | **enabled** | f/2.8 anamorphic = cinematic DOF |
| Motion Blur | enabled | **enabled** | 180° shutter |
| Resolution | 2048x1080 | **2048x858** | 2.39:1 anamorphic scope |
| Export Components | all | **diffuse+reflect+coat+sss** | Match rubber shader lobes |
