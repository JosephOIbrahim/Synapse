---
title: "MPM Auto Sleep"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "auto_sleep", "optimization", "performance", "simulation", "rest_state"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=MwSsXRof_7Y"
  series: "SideFX MPM H21 Masterclass"
  part: 2
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 262
duration_range: "0:02 - 11:04"
---

# MPM Auto Sleep

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=MwSsXRof_7Y)
**Presenter:** Alex Wevinger
**Part:** 2 of 18
**Transcript Lines:** 262

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=2)** Let's now talk about this new feature, the autosleep mechanism. Okay, so here we're going to start looking at this example where we have this spaceship coming out of the ground like this. And our ground in this example is going to be just this box that we're going to fill with some points. Can be soil, can be snow, whatever you prefer. Uh so again, like usual, we just start with this npm configure recipe. And in this case, right before connecting things, because you can see if I middle click here, this is pretty

**[0:35](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=35)** large. So it's like 100 meter on across the x-axis, almost 200 m across the axis. So we're just going to multiply the particle separation by 10 ju just so that we don't have a crazy high point count in this source. And then this is still uh taking a bit of time because we'll almost have like six million points being generated. And then this is going to be our collider. In this case, we need an animated rigid collider. So

**[1:07](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=67)** here we can blast these nodes. And we get this kind of setup. So um okay, another thing I'm going to tweak, I'm just going to multiply the And I don't think I'm going to need to touch anything else. So if I just start simming this. Okay. Can see we're running at about like 1.7 1.8 FPS, which is not bad, but we can improve that

**[1:38](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=98)** quite a lot with this uh sleep mechanism. So now on the MTM solver I can enable autosleep and we're just going to uh make our material start as passive or in this case we can even uh make it start as active. Doesn't change anything but we're just going to set this up as our visualization so we can see what's going on with the state of our particle. So we're visualizing the state of the point. And you can see now that we have this sleep mechanism enabled.

**[2:11](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=131)** If you look at your attributes here, we can see that we have this state attribute. One means active, then zero mean passive or inactive. And then there's a third state of your material which is called boundary. And uh because of how MPM works, we need this boundary state which is kind of an hybrid between passive and active. And you're going to see that in action very soon. So here our range of visualizations is going to be between zero and two.

**[2:42](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=162)** And uh we can just start the simulation. Oh, and this. Okay, I just want to stop this first. Okay, if I go back in the solver here and we look at the two settings that we have here, we have this velocity threshold, which means like what is the amount of speed in this case since it's just a float. So what is the the speed threshold which is going to reactivate the points. So this is scale dependent, right? So if you have a very small scene maybe this number can be very small but in this case this is very large scene so we can just multiply that

**[3:13](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=193)** by 10 like so. And this is the delay in terms of second. So half a second if we're running at 24 fps. So um after uh 12 frames where the particle is under this speed threshold the particle is going to be deactivated. Okay. So now if we go back to the first frame and we simulate, you can see that within a very small amount of time we went back to everything passive. And you can see that

**[3:43](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=223)** we're running at 3.4 2.3 FPS. So it's much faster, but it's because this is like the spaceship is not already in contact with the material. That's why it's going so fast. As soon as it starts hitting, you're going to see those uh I can pause here and I can zoom in a little bit. So everything that is green is active and purple is inactive. But you can see like this small sliver of particle here in red. This is the hybrid boundary particles. And this is necessary for MPM because we have this

**[4:14](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=254)** dual representation of particle and grid. And those particle and also those voxels that are here in red are going to be to have this dual uh representation where they are being updated like the rest of the active particle. So like their deformation gradient and their fine velocity is being maintained and updated but they are never integrated forward in time. So even if after a step of um MTM simulation it those particles should be moving in that direction they are going

**[4:46](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=286)** to stay put. So uh their attributes are updated but they are never being moved in space and this allows for those particles to be completely ignored from the npm updates and it also allows for those particles to be properly updated so they have like the correct boundary condition happening here. And now if we play again, so right now as we're activating like most of the points, there's definitely

**[5:17](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=317)** an overhead coming from this uh autosleep mechanism. So you might even go slower than if you were not using the uh autosleep. So u you have to be smart about where you use this feature. So you need to use it in situation where you know that a lot of the points are going to be deactivated for a long period of the the frame range. So at the beginning of this scene we had a lot of uh like wait time where most of the points were inactive. So we gain a lot of time here and also at the end of this simulation when the spaceship is going to be held static there's also going to be a lot of

**[5:48](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=348)** time where most of the point are held inactive. So in those specific situation you're going to gain a lot of u time. So for this specific scene, I have run the frame range from one to 250 and you get almost like well you get around a 2x speed up when using this u sleep mechanism with those settings here. So again really highly dependent on the kind of scene that you're using it on. And just keep in mind that if most things are just kept active and most

**[6:18](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=378)** things are moving throughout the frame range, you're not going to get uh any speed up from this and it can even decrease your overall performance just because there's a lot more things going on inside of the solver because it has to manage those boundary uh active and passive states and make sure that everything works with this sleep mechanism. But here, as you can see, as we're ramping in a point where most of the points are becoming uh passive, now we're almost at 2 FPS. So, we're

**[6:51](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=411)** benefiting again from this mechanism. And here, as we are tumbling around, you can see that most of the points are being held uh in this passive state, which is really good and uh will speed up your simulations. So that was one example. Another thing that you can do with this sleep mechanism is to activate with uh with this. So you can have some kind of a sagree activation. So let's

**[7:21](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=441)** say we have this model of crag like so. And again I'm just going to do our mpm configure. So crag is going to be our source. This collider is going to be again an activated not activated but animated So what we have going on here is we have Craig, we have our collider and we want this contact. So when the

**[7:52](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=472)** collider hits the knee of Craig here, we want uh everything to become activated. So we want Craig to react to this collision. But at the moment Craig is really like unbalanced. So if we just like start the simulation like that with everything active crack is just going to fall before the impact occurs and we don't want that. So just as an example if I I think I'm going to uh just increase a little bit the resolution by decreasing the particle separation. So if we look at what we have okay so this

**[8:23](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=503)** is what we have without any sleep mechanism. If I hit play, everything start starts falling. And then we have the collider hitting. I'm gonna just increase the stiffness Okay. And remove the display flag. So if we play, as you can see, everything is falling. And then we have the collider yet. This is definitely not what we want. Again, uh I'm going to make sure we can visualize the state of the particles. So on the mpm solver

**[8:55](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=535)** visualize color from attribute I won't this is good and I'm going to activate autosleep and here our velocity threshold we can multiply that by two to make it a little bit more aggressive on the deactivation and now if we play we can see that uh since everything is being activated as passive nothing nothing is moving. So our uh

**[9:26](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=566)** crack model is holding this pose very unbalanced pose which is exactly what we want. And then as soon as the collider hits you can see that everything gets activated in one go and the reason why it's working so well is because of the many many substeps that MPM is computing behind the scenes. So if you look at the detail attribute you can see that we're running at 226 substeps. So what happens is as soon as this collider is hitting the knee, it's not going to activate this point right here. So it's only like on the first substep after the impact,

**[9:56](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=596)** it's only going to activate those point here. But then the substep after that, then those points are activating nearby neighbors because they are now exceeding this speed threshold. So progressively within those 226 um substeps, it's just going to propagate this impact wave throughout the whole material which is going to activate the whole model within a single frame. But this is really thanks to the large amount of substeps that we have uh going on behind the

**[10:27](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=627)** scenes. And then when we look at this in context and we just hit play, we see everything being activated. Things are collapsing. And if we are patient a little bit and we let the simulation run a tiny bit, you're going to see some of those uh cluster of particles being deactivated again like what we're seeing here. And eventually everything is going to be uh fully passive and the sim is going to run much faster. As you can see, the FPS is already uh increasing quite a bit. We still have some pieces. And yeah,

**[10:59](https://www.youtube.com/watch?v=MwSsXRof_7Y&t=659)** when everything is almost deactivated. Okay, now we're running at 13 FPS. So yeah that is it for uh this sleep mechanism.
