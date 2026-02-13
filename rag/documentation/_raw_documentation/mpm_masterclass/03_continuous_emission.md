---
title: "MPM Continuous Emission"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "continuous_emission", "particle_emission", "source", "fluid_source"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=AGjuRlj5sm4"
  series: "SideFX MPM H21 Masterclass"
  part: 3
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 169
duration_range: "0:02 - 7:46"
---

# MPM Continuous Emission

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=AGjuRlj5sm4)
**Presenter:** Alex Wevinger
**Part:** 3 of 18
**Transcript Lines:** 169

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=2)** Let's now take a look at continuous emission expansion. Okay, so in the scene we have this wine glass and we have this source, the sphere here and we're going to try to fill this glass until it overflows. So this is the goal. Now if I just again do mpm configure like we always do and uh this is going to be our collider. This is our source. And I'm going to need a lot more

**[0:32](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=32)** resolution for this. Like that. So for in terms of the source, it's pretty good. For the collider itself, we're just going to increase the resolution on the collider directly. And uh as always, when we have a thin collider like this, it's good thing to enable particle level collisions. And we use a default method there. It's going to work perfectly fine. Um, just going to make sure that I change a little bit the visualization. I want to look at the speed of the

**[1:03](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=63)** particle from zero to one. And I'm going to look at this color scheme here of white water. Good. Um, I'm going to disable the collider visualization so we can just see this uh transparent version of it. And now if I just hit play. Okay. Well, of course, we don't have uh the proper material. So, can set it to water. And also, we only we are only emitting once at the moment. I want continuous emission. So, now if I just

**[1:34](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=94)** emit this is what we have. And we are adding some material here, but we're not uh able to fill the volume of the glass. And uh just give you a little bit more explanation about why this is. So um okay let's first start with a voxel. So remember with npm you have this dual representation of voxels and particles. So this is let's say one voxle and these are your particles in that

**[2:07](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=127)** voxil. Okay. So since npm is simulating this continuous material and we have this dual representation of voxels and particles and usually we are packing like around eight particles per voxels. There's no point in adding more particles. Like if if even if I add like a lot of particles like this in a single voxil, all of these are only going to contribute to a single voxil and after that the information from this voxil is scattered back to the particles. So having a bunch of particles packed like that is just going to cost more in terms of computation, but it's not going to

**[2:39](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=159)** help you get more details. So what's happening by default with npm is anytime that you're trying to add new particles it's going to look at uh its neighborhood and if there are already particles nearby it's not going to allow it. So if u so let's say if I'm I'm trying to add this particle it's looking around and it's seeing it's seeing okay I see this particle this particle here so it's like within uh too close to my neighborhood so there's no point for me to exist because I'm just going to cost

**[3:10](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=190)** computation time but what happens is uh instead if we like if I just do a couple of undo. So if I if I'm able to push those particle particles away, right? So if I source some internal pressure here and I get these particle to move, let's say here, here and there. Now if I try to add a particle here, there's nothing in this neighborhood, right? Like those particle has been have been moved away. So now I

**[3:40](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=220)** can introduce new particles there. And if I do that repetitively like on every substeps at some point I will be able to go um and to fill a container by adding more particles because every single step if I'm sourcing internal pressure and I'm pushing everything away from the emitter I'm able to uh slowly like grow this volume of emission. And this is exactly what we're trying to do in Udini. So if I go back to this um now what we can do is we select this MPM

**[4:12](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=252)** source and we activate this overlapping emission and uh we have this expansion parameter now and just like if I keep it at one and we play this it's not going to do a huge difference like you might be able to see it like it's slowly growing but very very little. But if we uh crank that up to 25, now we're sourcing a lot more uh internal pressure. And now we're getting what we want. So we're able to have those particle

**[4:44](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=284)** uh push away from each other. This is creating a void. And now when we're trying to do this continuous emission since we have those void pockets of no material basically, we are able to introduce new points. And this is what allows us to do this. But you're not only limited to liquid materials, right? So I could just take all of this, copy it over. And now instead of uh simulating I'm just going to kill the simulation. So instead of simulating liquid, I can do um change

**[5:14](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=314)** preset. And let's do snow, right? And I'm going to change the visualization of this. So I'm just going to do a point wrangle here. And I'm going to store the Okay. Right on the npm solver itself. I need to go to output and make sure that this is And now I'm just going to do another

**[5:46](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=346)** wrangle here. And we're going to say CD And we're going to do Bert. And I just want to wrap around. So, as soon as we reach the end of the ramp, I just want to wrap around and sample again from the beginning. So, we're going to make this a color ramp

**[6:16](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=376)** like so. and we're going to pick the infrared preset. So now if I play this, we are filling the glass with this new material which behaves totally differently than the the water preset that we had. And we have this cool visualization where we can see depending on at what frame or at what time it was emitted, we see a different color. So it allows us

**[6:46](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=406)** to track how things are evolving. And if we are patient enough, at some point this should break and create some cool visual. Cool. So yeah uh this is just to show you that you can use this uh feature to do a lot

**[7:18](https://www.youtube.com/watch?v=AGjuRlj5sm4&t=438)** more than just like filling a container with water can use different type of materials and achieve very cool effects. Um and just know that the demonstration that was shown for the launch of H21 like this cookie and cream demo there was some whipped cream being added on top of the drink at the end. And this feature of continuous emission expansion was specially designed to achieve this shot. So yeah, if you need to do some whipped cream, definitely look into that feature because it's going to be very
