---
title: "MPM Pumpkin Smash"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "pumpkin", "smash", "destruction", "organic", "fracture", "debris"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=OVQAAlh-3s8"
  series: "SideFX MPM H21 Masterclass"
  part: 12
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 283
duration_range: "0:10 - 13:02"
---

# MPM Pumpkin Smash

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=OVQAAlh-3s8)
**Presenter:** Alex Wevinger
**Part:** 12 of 18
**Transcript Lines:** 283

---

## Transcript

**[0:10](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=10)** Okay, let's now take a look at this So, first thing perhaps unsurprisingly is pumpkin. And then here uh I'm splitting the pumpkin into different layers, different components. So, first thing is the outer skin like that. And we have a little bit of thickness to it. Here we have some flesh. This is a little bit hard to read right now. So I can show you how it looks.

**[0:41](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=41)** Oop, sorry. How it looks inside. So um yeah, this is not that much biologically motivated, but I'm just trying to get a lot of those fiber uh going from the outside skin toward the core of the pumpkin. This is going to influence how things are being simulated and also how things are going to look at render time. So yeah, as you can see just trying to get as much fiber as possible. And finally the last part are the seeds and I have modeled just a little model of seed like this and uh scattered it

**[1:14](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=74)** oriented toward the center like so. Very simple stuff. uh and in terms of uh how we use that in our simulation here. I'm doing a little trick where I'm actually not using directly the points that are coming out of the npm source as you will see. So I'm taking this flesh model. I'm just keeping the points and here I'm fusing the overlapping points. So we go from 40 million to 9 million and this is all driven by this particle separation on the mpm container. And

**[1:46](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=106)** then I'm uh defining my uh material here that I want to simulate. But then I'm just going to take those MPM attributes and transfer them over to those points because this is the point I want to simulate. But this is where I'm configuring the material. So you don't really need to uh use the points that are coming out of this node directly. So this is what I'm doing here. And we get our source here. Good. I'm assigning a color here. I'm going to prune the flesh that are overlapping with the seeds that we have here.

**[2:20](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=140)** Uh on this side here we have our flesh. Uh not flesh but skin. Everything gets merged together. Again I'm doing another step of uh deleting the overlapping point. So now let's go from 14 million to 12 million. And finally I'm increasing the stiffness of everything. And I'm sure this was derived from just iterating on the simulation, trying to get something that looks cool, and I needed everything to just be a little tighter and stiffer. So, I increase everything. In terms of

**[2:52](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=172)** the material themselves, um, we have this is just like the rubber preset. And those two, uh, the skin and the flesh are kind of similar. And there's no like magical recipe here. I just like started from the snow preset and iterated on it until I got the look that I wanted. You can see I have like zero compression hardening, but on the skin I have some. So yeah, again, no magical recipe. It's just a matter of tweaking until you get the the look that you're after in your simulation.

**[3:23](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=203)** Here we have our collider. So this is going to be our hammer that is going to So here we have it. Uh this is being animated kind of in real time. This is how I like to work. So I'm just making sure that I have the the speed that I would expect the hammer to hit in real time. And then uh this is where I apply the um time scale of the simulation. So I'm going to get my slow motion from

**[3:58](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=238)** Okay. For the solver itself, I have this material condition reduced to 7. So just ramp up the substeps a little more aggressively. I have my time scale here that is driving many different things in this scene. All the points that are going too far away, well hitting the walls of the domain are going to be deleted. And I think that's pretty much it. Everything else is at default. The output is just taking care of removing some attributes. And that's it. This is what we're we are caching.

**[4:29](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=269)** And if we look, yeah, we look at a frame like this one, this is what we get. Looking good. And here I'm starting the simulation at frame 32. So I'm adding this clamp to first frame just to make sure that the we still have some data on frame one when because uh like nothing is going to be simulated until we reach frame 32 but we still want to see our pumpkin and the impact starts at frame 32.

**[4:59](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=299)** After that we're pruning uh this CD attribute and we are applying the time scale to our velocity. So if we [clears throat] are rendering this directly, we want the velocity vector to represent how much the points are moving in space. And since this is a slow mot, we need to multiply the velocity by this uh multiplier here. Here we are just So I'm just going going to load one

**[5:30](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=330)** frame to show you how it looks. Okay. So this is our collider. And here in terms of the settings, yeah, everything's at default. It's just a simple npm surface at default. Nothing changed. Um, and here we are setting up our uh debris source. Again, we have our MPM debris on this side. We are removing the seeds because we don't want to uh emit any secondaries from the seeds. And here we are kind of

**[6:00](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=360)** doing the opposite operation. So we are reapplying the scale up of the velocity vector because we are going to simulate in slow motion. So for things to move at the correct speed in a slow motion simulation you need to have the proper velocity vector that represent how things would be moving in real time. So just if I show you so this is what we were getting as input and now we're dividing by this time step to recover our proper velocity vector for the real time.

**[6:32](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=392)** Now if I look at the output of this node I think most things are all set. Yeah this is pretty much the default on everything. I've just increased a tiny bit this uh minimum speed to have uh like slower points not being included and I have reduced those two parameter to get just less point being generated in the pointer replicate and I'm also just keeping 10% of the generated points from this node and that's it. So now we can just see if I go back to automatic update we can see the kind of points

**[7:11](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=431)** and oh you can also see maybe another detail that is important can also see that this time scale uh is grayed out because it's being imported from the uh this branch here. So it knows that this is a slow mot. So that's why you don't like even if the the vectors are really strong when you do this here. Oops, sorry. This like spread point along velocity, it's not going to spread the point from ear to all the way there. Like it's doing a smaller spread because it knows that this is a slow motion shot. If you didn't have that, it would

**[7:44](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=464)** like spread the spread the points a lot further forward. Okay, so this is good. um them in terms of secondary simulation. This is a very basic pup uh solver. Here I'm computing the packing of the points so that points that are densely packed are less affected by this air resistance. And I'm handling the collisions here. But feel free to use like just a static object like that to do your collision. It's going to work

**[8:16](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=496)** Okay, here we have our secondary simulation. This is this is going to be just like water droplets, just some kind of spray to add this very high uh frequency level of details. Again, I'm multiplying by the time scale. So, we have smaller velocity vector. So, this is ready to render. And finally, I'm just keeping 10% of the points like so. So this is what we're going to use to render our secondaries. And the

**[8:48](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=528)** last bit of the setup is meshing our pumpkin. And I don't know if you if you've watched the uh first npm master class, you might remember that this used to be like very involved. But now most of the technology is just like embedded into those post simulation nodes. So it makes those uh uh node tree very very compact and I think it's it's really nice for the users. I mean, I hope it is. You can let me know. Um, and so yeah, if we pick a more interesting

**[9:23](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=563)** Okay, good. So, we're splitting uh the pumpkin by components. And here we have this skin mesh. Uh, and there's a couple of things that is happening here. So first thing I'm computing the depth because at render time I'm going to vary the color of um of this surface using the depth of the skin. So I want like one color from the interior and one color for for the outside and I want to smoothly transition between those two colors. That's why I'm computing the depth here.

**[9:55](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=595)** And uh I'm also piping this rest model into the third input to transfer the UVs. So this is why. Okay. So, I'm just going to cook this Okay. So, here you can see the UVs are

**[10:26](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=626)** properly transferred. And in terms of the par that we're using on this uh polygon mesh, we are transferring this dep attribute for the from the mpm particles. We're transferring the UVs from this rest model. And in terms of surface parameters, we are not doing any dilation. Uh so this could be unchecked. Uh we are doing some smoothing, some erosion. And uh we are also using this mask smooth and we can visualize what is being protected from this smoothing. So

**[10:58](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=658)** if I check the mask for the JP attribute, so everything that is tearing or stretching, all of this in blue is being protected. So this is not going to add to receive any smoothing from this part here. And we also have a mask with curvature. So again, everything that is in blue like that is going to be excluded from the smoothing. This is exactly what we want. We just want those

**[11:28](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=688)** terms of the flesh, I don't think we're doing anything fancy here. Um, let me check the npm surface when we're Okay, so this is cool. Uh, we have our like fiber look uh for our flesh. So, this is exactly what we want. It's going to look good for a render. And then if we look at the npm surface, we have increased the additivity by a factor of 10. So we're trying to get as

**[12:01](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=721)** little uh amount of polygon as possible because I think this is already yeah like 28 million polygons. So we try to reduce this so it fits on a GPU memory if you use XPU. And here just very simple VDB from particles with a couple of filters nothing special. In terms of the seeds, we are using this npm deform pieces in a special way. So not in conjunction with the npm post structure. We are directly using our receipt just making sure that we have a name assigned

**[12:33](https://www.youtube.com/watch?v=OVQAAlh-3s8&t=753)** to each of them and then we can simply use this mpm deform pieces to move them in space. So then when we toggle, so this is our seed points, our MPM points simulated and these are our models with UVs and all that you might need for rendering. Well, I don't think that these have UVs, but all of those look attributes would be already assigned to this geometry, which is what we want. Cool. And then we're just baking that down to a poly soup. And
