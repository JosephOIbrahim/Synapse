---
title: "MPM Surface Tension"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "surface_tension", "fluid_sim", "droplets", "mpm_solver", "viscosity"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=HAv1t7q7VRk"
  series: "SideFX MPM H21 Masterclass"
  part: 1
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 278
duration_range: "0:02 - 13:17"
---

# MPM Surface Tension

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=HAv1t7q7VRk)
**Presenter:** Alex Wevinger
**Part:** 1 of 18
**Transcript Lines:** 278

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=2)** So let's first take a look at our new features. Let's jump in Udini. So this is the IP file that you have access to and you can follow along as I'm doing these demonstration. So this is the subnet containing the new features and the first thing we're going to take a look at is this surface tension feature. Okay. So let's say you have this scene with a bunch of leaves like that and you have a droplet on top of those leaves and you want to simulate that using surface tension. First thing just npm configure.

**[0:32](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=32)** This is something that we're going to use a lot. So it gives us the that And then our collider is going to be the leaves. So we can just remove this box. And then the source is going to be this And then uh first thing we can see is that our collider is lacking a lot of resolution. We don't see the leaves at

**[1:03](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=63)** all. So uh we can try to increase the part well decrease the particle and take a look at our droplet as well. So how many points how much resolution do we want here? We can again reduce this. Okay. I think this starting to be pretty good. And then if we take a look at our collider, still not properly resolved. So what we're going to do since this is a very thin collider, we're just going to overwrite the

**[1:34](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=94)** resolution here on the MPM collider. And uh so right now, right now we're at this amount of resolution. So maybe I like so. Oh, and here you can see that we have like a probably resolved the collider. So, this is good. And then if we look at our MPM solver, everything looks fine. Next thing, I'm just going to pick the water preset

**[2:06](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=126)** like so. And here I can visualize the particle a little better by just sampling the speed and picking this uh like so. And now if I play, this is what I have. So we see already that we have some water flowing through the collider. So this is obviously not what we want.

**[2:36](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=156)** For that we can select the mpm collider and just make sure that oh no in fact this is on the npm solver under the collision tab and we can just enable particle level collision and this default of velocity base move uh move outside collider will be perfectly fine. So we just need to go to the first frame and we hit play. And now we have the water probably flowing on top of the collider not going through. This is perfect. But we totally lose the shape of our droplet. And uh this is actually

**[3:06](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=186)** what we want. We want to do this like this small scale macro shot with the water holding onto itself with surface tension. So for that we can just enable surface tension on the solver like so and uh by default this is using the pointbased method. This is a little bit more expensive but this is the exact same implementation that we are using in vellum. So this is working directly on the points and the points are looking at their neighbors. So um yeah the

**[3:37](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=217)** resolution of the surface tension with will scale with the resolution of the point cloud. Uh so this is the most stable version of the implementation of surface tension with npm. But just know that it will take more VRAMm if you run on the the GPU because each of those points need to be aware of all of its neighbors. So it's growing quite fast in memory. Okay. So let's just run that. See how it looks. And right away we have something that looks better. But we can maybe

**[4:08](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=248)** boost that a little bit. So maybe times five, And here we're really starting to have No, it could be even more extreme.

**[4:39](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=279)** And here we might want to see some of the water like hanging uh from this leaf. So what we can do is increase the friction and the stickiness. And don't be afraid to put those value very high. H we can even push that even further because the surface tension is going to try to um keep the points closer together. Right? So uh it's it's going to push the points away from the collider a little bit. So this is why you might need to ram those

**[5:10](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=310)** values very high because the points are are like levitating a little bit over the collider. So by increasing those value to very very high values like that, you're going to be able to reach a decent amount of friction and stickiness. So let's take a look at what Okay. So, we can see that we have some points that are trailing behind. That's good. And are we going to get what we're

**[5:41](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=341)** looking for here? Maybe to have some droplets falling from this leaf to this Yeah. This is exactly the kind of detail that we're looking for. like this this droplet falling and then as it's detaching from from the leaf it's creating another uh like another droplet midair. So yeah that's exactly what we're looking for and here on the ground uh you can see because of surface tension it's also like creating those cool uh pattern with the water. Okay so

**[6:14](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=374)** this is one example and then um another thing that I want to talk about is this uh multihase option. Um so again npn configure we start with that all the time and let's go to the first frame. So now we have two spheres on top of each other like that. And uh we're going to assign each of those sphere with a different phase such that surface tension is only happening within each of those materials. So I want this sphere to be attracted to itself and this sphere

**[6:47](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=407)** attracted to itself but not u I don't want them to be attracted one to the other. Right? So for that I'm just going to duplicate this mpm source and then connect those two spheres. I'm going to assign both the water preset. But here you see we have the surface tension and phase option parameters I mean. So I'm just going to enable them. And then the first material I'm going to set surface tension to zero. And the second one surface tension to one. But then I'm going to increase the phase from one to two. So you can

**[7:19](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=439)** really see that as a like a ID for the material. So those two material are going to be seen by the solver as two different materials that shouldn't um apply surface tension one to the other. Right? Okay. So just for visualization, I'm going to lay down a color node so we and one blue. Then I can merge them together

**[7:57](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=477)** We're going to get rid of this collider. Multiply that by a crazy number so we can actually see something. Okay. And right away what you see is that this blue material has a very large amount of surface tension. This green material has zero surface tension. But then just keep in mind that MPM is general in general is very sticky

**[8:28](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=508)** because all of the materials are still using the same underlying grid. So when it's doing its transfer of velocity and momentum from particles to grid and then back from the grid to the particles, uh there's going to get some uh interpolation issues where if you have a lot of blue particles with surface tension and you have a green particle nearby, even if the green particle doesn't have surface tension, it's going to receive a little bit of that motion and momentum because of grid interpolation. So yeah, the this explains why you have some green particles that are gathering

**[9:00](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=540)** close to the the blue material, but overall the green material is really behaving like water without any surface tension or another liquid. And the blue material has a lot of surface tension. And this allows you to create those very intricate and detailed pattern that could be useful for look development if you're trying to create like some weird magical liquid or whatever. uh it's just another tool in your toolbox to create those cool uh kind of effects. So this is for the multifphase. It's also shows you that you have this control here per

**[9:31](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=571)** material if you want to play with the surface tension and this phase. And at this uh point the mpm solver uh surface tension strength just becomes a multiplier on top of what is coming from this uh mpm source in terms of surface tension here. Okay. And last thing is um I want to discuss about I want to talk about this new method. So just again lay down this mpm configure.

**[10:05](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=605)** So as I previously talked about we have this other implementation this grid grid based implementation and in this case we have an example of a small I mean a lmet to scale that is just rising up like that and we have this uh box which is Um, so I'm just going to define the domain with from this water. So this is going to be our domain.

**[10:36](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=636)** Connect that to the mpm container. It's going to be a closed domain. Then this is our collider. It's going to be animated rigid collider. And this is our water. So I'm just setting the preset to be water. And if I go back to the first frame and I view that. Okay, we're lacking a lot Okay, this seems more appropriate. Maybe

**[11:06](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=666)** like that's even better. Okay, I have the feeling this is going to be too slow. Okay, [snorts] this is going to be our compromise, I think. And we have our Yeah, it's a little bit slow, but uh So if we now select this grid base approach and here I'm going to reduce it tiny bit

**[11:37](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=697)** because I think this uh implementation I will reduce the friction here and increase the stickiness quite a bit on the collider. [snorts] And here again we can cheat this detection distance and multiply that by two. And now if I hit play, I'm most likely

**[12:08](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=728)** going to pause this. Oh, and uh just just so you uh pay attention like right before changing from this grid implementation, I run a couple of frames with the other implementation and it was way slower. So as you can see this method, this gridbased method is much faster than the other one. But yeah, a little bit less reliable. So you can see like gain in momentum sometimes. So you can see like a a blob of water starting to move in a in a like unmotivated

**[12:38](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=758)** direction because this implementation is a little bit less stable. But in this case for just like drips falling from a collider back into the main body of water. You don't really need that much accuracy and this method works really really well. So as you can see we have like those cool tendrils of water falling from the model. uh and gathering into droplets as they are falling midair. So yeah, this is definitely the kind of detail that you're looking for when you

**[13:12](https://www.youtube.com/watch?v=HAv1t7q7VRk&t=792)** want to do like drips, layers from objects emerging from the water. So yeah, that's it for surface tension. [snorts]
