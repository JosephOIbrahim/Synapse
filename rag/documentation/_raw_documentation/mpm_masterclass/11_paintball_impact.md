---
title: "MPM Paintball Impact"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "paintball", "impact", "splatter", "viscous_fluid", "collision"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=zj5ANrtD-X8"
  series: "SideFX MPM H21 Masterclass"
  part: 11
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 248
duration_range: "0:01 - 10:16"
---

# MPM Paintball Impact

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=zj5ANrtD-X8)
**Presenter:** Alex Wevinger
**Part:** 11 of 18
**Transcript Lines:** 248

---

## Transcript

**[0:01](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=1)** Okay, now we're all done with the basics. Let's now take a look at some practical demo scenes so you can see how to use all of these new goodness in H21 So, we've been very patient looking at all the basic stuff, but now can look at more exciting examples. Uh, okay. So, just so you you know, we have all of these different scenes that I showed at the very beginning of this master class, and we're just going to go through the

**[0:33](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=33)** setups one by one to see like the important bits that you should know about. Uh here you have the uh global control on the resolution. So, the videos that I was showing at the beginning is with this particle separation multiplier set to one, but here just to speed things up a little bit, I increase that to two. And um it's just going to make the resolution like 1/8 of the final resolution in 3D. So yeah, just going to make things a little bit more interactive. And here if

**[1:04](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=64)** you are looking for example of how to use let's say the uh npm surface, you can see I have for each of those example I have listed all of the different features or new postmission nodes that are being used in each of the examples. So if you're interested in the sleep mechanism for example, you can see that it's being used here in this wolf snow example that is right here. Uh so yeah, let's jump right in in the first one. So this paintball impact example. Uh these scenes I'm very unoriginal like the the

**[1:36](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=96)** layout of those nodes is always the same for each of those scenes. So it's going to be uh very predictable every time. So I just have this subnet where I'm doing everything in a single subnet. And then you have the rendering setup like this Solaris setup here to get the renders going. And you also have a top network where you can inspect the different uh dependencies in task and the different steps that you need to go through in order to generate the final render. Um so yeah, that's pretty much it. And

**[2:08](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=128)** now if we just look at this scene, uh yeah, this is it. Like this is the whole setup. It's simple as that. Uh some scenes are going to be more complex, but for the the paintball, it's relatively simple. So, um and there there are not a lot of tricks in this one. It's it's fairly uh basic. So, I start with a circle and then I just keep the line going around it. Then I'm going to sample three points and those are going to be the initial position for each of my paintballs that are going to it in the middle. Then I jitter that a little bit just to add a little bit of

**[2:41](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=161)** randomness and variation. Then I'm going to set up the velocity. So they all go toward the center. I set also the P scale and some uh ball ID that is going to be used to set the colors and also uh for the rendering step of things. Then I copy some balls here. These are going to be the paintballs. And at this point I'm just scaling everything by 100. And the reason for that is sometimes when you work at a very small scale you can run into issues with numerical precision and

**[3:12](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=192)** numerical accuracies. So, just to make sure that we're not running into those edge cases, there's no real reason to work in world scale for this type of effect since we're doing like a very very slow motion shot. Uh, so I'm just scaling everything by 100. I'm going to do the same thing for gravity and for time scale. I'm just going to adjust everything so it still works like it still behaves like we're in small scale, but we're going to avoid some of the numerical issues that we can run into if we were working in world unit.

**[3:43](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=223)** Okay. So, after that, I'm adding a little bit of variation on those. Uh, like those paintballs are a little too perfect for me at the moment. So, I'm just adding a little bit of noise to break them up. And then I'm smoothing that back just just to have a little bit of deformation. It's going to add some intricacies and some details to the simulation. And after that, I'm just adding a level of subdivision. And these are my final uh paintballs. After that we need to go to uh the simulation step. So first thing is the

**[4:15](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=255)** shell. So the the rubber shell around each light balls. And for that I'm just very simply using the rubber preset here. And I'm multiplying the stiffness up by 10. So the the rubber is very very solid. And um I'm also using this type surface. So this is empty inside. If we go into it, you can see it's just like a shell basically. And I'm also adding plenty of relax situation to make sure I have good coverage. It's not perfect. So you can see we still have some holes

**[4:46](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=286)** here and there, but when meshing this is not going to be visible like those points are going to fill and close this gap. Okay. And here we shrink a little bit. So that was the the original paintball. We shrink that a tiny bit and then we fill that with paint. And uh again like there there's no nothing fancy here. I'm just uh like using the water preset. Uh I'm multiplying up the incompressibility just to make the liquid um little more stiff. So it it will lead to more

**[5:18](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=318)** explosive behavior because it will tolerate less compression. And this is what we want. We want to see some cool splashes. That's why I'm cranking that up a tiny bit. Um and again you can see that I'm I'm also keeping this ball ID attribute. and along other things because it's going to be used in rendering. In terms of the domain, I'm just setting up a large enough domain and I'm setting all the bounds to delete. So any points that reach this bound is going to be killed.

**[5:49](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=349)** And um that's pretty much it. On the solver itself, we have activated surface tension. We're using the pointbased method because this is the most reliable option for us and it is pretty um strong currently. So um for that we have increased the minimum amount of substeps because going below that value was leading to some instability. We have also decreased this material condition again to make sure that the solver will will more aggressively ramp up the number of

**[6:19](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=379)** substeps if required. And we have also introduced um two global dub substeps. And as you can see our time scale is multiplied by 100 following the scale up that we've done. And also our gravity is reduced by 100. So everything should be uh uh behaving like our original small scale scene. Then there's nothing else being changed here. Collision we have removed the ground plane. and output. Again, we're

**[6:49](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=409)** making sure that this ball ID attribute is flowing through. if I display just a point, this is what we get in terms of simulation. And this is exactly what we're looking for. So, the surface tension feature really allows us to create those nice tendrils of liquid. And uh it's really going to look great when we render that

**[7:19](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=439)** with like some transparency and subsurface scattering. This is exactly the kind of detail we're looking for. And again, just remember that we're currently working in this halfres particle separation. So you can get a lot more details out of it if you set that this global multiplier to one. After that, we correct for the velocity. So here I'm I'm applying this uh time scale to our velocity because we are like rendering

**[7:50](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=470)** in slow motion. So we want uh we don't want the motion blur to um to be evaluated like if it was a real time shot. So we need to multiply by time scale here. And we're pretty much done with the simulation from this point on. It's just like okay this is our sim. We split the shell on one side. So this is like the rubber shell. I'm going to iterate over each shell separately to mesh them. And this is the result that we get for

**[8:22](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=502)** the rubber shells. Currently on the MPM surface, I'm just u generating a poly soup for Jeffdam with a little bit of adaptivity to reduce the poly count. And I'm using this u VDB for particle method with a little bit of filtering. And that's it. For the paint itself, I'm doing just one step of attribute transfer here just to smooth the colors a little bit because I want to simulate this color blending between the different paints. So yeah, just

**[8:53](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=533)** going through this attribute transfer here. And after that uh going through the MPM surface again just trying to extract this poly soup representation of the paint. And this is what we have. Again this has been cached here so we don't have to wait every time. And uh yeah, here you can see that the

**[9:24](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=564)** filtering um settings are more aggressive. So more dilation, more erosion, more smoothing. I'm really trying to uh kind of get this look of surface tension uh surface where like nearby particle are going to connect with the small tendril. So that's why I have those two value increase a tiny bit. And for the rest in this case, I have removed the additivity. I think this is for to avoid any kind of flickering coming from the um color variation. So like let's say if if here

**[9:58](https://www.youtube.com/watch?v=zj5ANrtD-X8&t=598)** I have a I have some ramp going from red to green and the polygons are changing from frame to frame then you might not get the exact same transition from the two color from frame to frame and it might introduce some flickering. So in this case I think I have reduced I have removed completely the adaptivity to solve that and here we're just transferring the CD attribute.
