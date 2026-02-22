---
title: "MPM Debris Source"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "mpmdebrissource", "debris", "secondary_elements", "chunks", "fragments"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=83EffKFYeCU"
  series: "SideFX MPM H21 Masterclass"
  part: 7
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 244
duration_range: "0:02 - 10:33"
---

# MPM Debris Source

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=83EffKFYeCU)
**Presenter:** Alex Wevinger
**Part:** 7 of 18
**Transcript Lines:** 244

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=83EffKFYeCU&t=2)** Let's now move on to the npm debris source. Okay, so here we have the simulation that we just showed with the the MPM surface. So here is our point representation and here we have our SDF and velocity volutric representation with two VDBs the surface and the velocity field. Okay. So if I just drop a npm debris source, this is very similar by the way to this uh I know you are probably familiar with

**[0:32](https://www.youtube.com/watch?v=83EffKFYeCU&t=32)** this debris source that we use in RBD. Like this is a very similar workflow but for MPM and the the only uh input that you really need is this MPM simulation. So the particles but uh this is also very recommended. So the second uh input for the MPM uh surface for like the collision representation of the simulation here is also recommended and I'm going to show you why in a moment. So if we just look at the output that we get and uh just to start I'm going to disable

**[1:05](https://www.youtube.com/watch?v=83EffKFYeCU&t=65)** everything so we can just focus on one Okay. So uh if you look at if we look at the top we have this start frame in this time scale. You don't need to set that because it's coming from a detail attribute from the mpm sim. But if you want you can override it. Here we decide uh like the default is to emit an integer frame only. And the first important tab is here where you prune point. So this is basically where you select the points that you're going to use to do secondary emission to add this

**[1:35](https://www.youtube.com/watch?v=83EffKFYeCU&t=95)** um because this yeah this is not something I mentioned at the beginning but this node is used to add this uh higher frequency of details to your simulation. So you have your MPM points that have a certain resolution and then you emit secondary debris just to add more finer details to make it more realistic and more detailed overall. So um okay so the prune point first thing is this uh minimum stretching. So this is using our GP attribute that we

**[2:05](https://www.youtube.com/watch?v=83EffKFYeCU&t=125)** uh that we know from npm. So this attribute here GP and this is basically detecting where things are breaking and stretching. So we can u increase this value and be more like conservative and emit less points or reduce in reduce it and be more permissive and pick up more points to do emission. So right now I'm going to pick this uh we can also emit based on speed. So as you increase this it's going to reduce the amount of point because this is the minimum speed to uh emit from and when we enable this max

**[2:37](https://www.youtube.com/watch?v=83EffKFYeCU&t=157)** distance to surface. This is exactly why we need this input here. So if I go back uh if I go to the drawing board here and I reset. So uh what we have here is our snowball. And let's say for example that these are all good candidates for emission. um this option. So this parameter will say okay if I define this distance

**[3:07](https://www.youtube.com/watch?v=83EffKFYeCU&t=187)** to be the maximum distance from the surface it's going to consider this distance from outside and from inside as like a banner around the surface where I'm allowed to do particle emission. So okay this is like a very bad drawing but you can see like looking at this banner around the surface we can easily see that this is not going to be used as an animation candidate uh either this one is not going to be used and not this one this one but only those sitting in this

**[3:38](https://www.youtube.com/watch?v=83EffKFYeCU&t=218)** banner around the surface and it makes a lot of sense like a lot of times you want to do your emission like that because you don't want to be emitting debris from within the collider depending on how you treat the collisions in your secondary system it might create like very weird reaction where this particle is going to be projected within a single frame to the surface and it might look very odd. So it's a good uh good setting to use. So here you're defining this maximum distance and we can see the effect of it by just

**[4:08](https://www.youtube.com/watch?v=83EffKFYeCU&t=248)** enabling it and disabling it. So all of these particles that were like too far inside our snowball here are being pruned when we enable this. And here uh if you look at the tool tip you can see that this um distance is also defined in terms of dx. So in terms of voxal size of the simulation. So it will scale with the the scale of your scene. So if you have like a very massive scene um this one will represent the the size of a

**[4:38](https://www.youtube.com/watch?v=83EffKFYeCU&t=278)** voxel in the background grid in npm. So you don't have to change it depending on the uh the scale of your scene. And finally we have this ratio to keep. So if you just realize that you have too many points that you're emitting, you can decrease that and just emit like let's say 50% of the points. Good. Then after that we have isolated points like that which is good. But we might want to replicate them based on those two attributes. So based on stretching and speed and this is exactly what you have here. So you can enable

**[5:11](https://www.youtube.com/watch?v=83EffKFYeCU&t=311)** those two here. And as you can see we're duplicating we're replicating those uh points. And just to visualize more uh what we're going to get in the end, I'm just going to enable the spread point along velocity. And this is to prevent the emission to be too um uh to have too much stepping in there. So again, if I go back to the drawing board real quick. So by default, you have like let's say this is your frame zero, you have a bunch of points and this is your frame one, you have a bunch of points, frame

**[5:43](https://www.youtube.com/watch?v=83EffKFYeCU&t=343)** two. Uh so as you can see if you're emitting like that without spreading along the velocity you're going to get a lot of stepping stepping in your emission trail and it's going to look very odd and unnatural. This is different than if we spread those points along the velocity vector uh within the range that should be traveled between two frames. Then we get continuous emission like that. And we're going to get like a very uh beautiful straight line of emission. And this is

**[6:14](https://www.youtube.com/watch?v=83EffKFYeCU&t=374)** Um so yeah this is what we're seeing here and um yeah depending on this is really something you can adjust to your taste. So by default as you can see it's grabbing like this minimum stretching and setting that as the input of this remap and the output is just this number multiply by 10 by default. This is exactly the same thing for the speed and then those two uh those two range are being remapped between zero and one and then uh this is being used in a point replicate. So if you want more

**[6:45](https://www.youtube.com/watch?v=83EffKFYeCU&t=405)** replication happening based on the stretching you can increase this or decrease this. Same thing for the speed and just adjust that to get the amount of point that you want. Um and here we're just uh dealing with some attributes. So we're stripping everything but we're keeping the pcale velocity and orient. uh orient is currently not coming in from the simulation, but if you want to be instancing debris onto your npm particles, uh this could be coming in. You can also initialize it from here. So

**[7:17](https://www.youtube.com/watch?v=83EffKFYeCU&t=437)** if you want to be um using orient in your pop simulation, you can just initialize random orientation there. And finally we are multiplying down the P scale by around a third of the P scale of the npm points because as I said previously we want this to be like a high frequency uh small scale detail. Okay good. So uh I have already set up this um popnet such that the first input is going to be our emission point and our second input is going to be our collider. So here we can just very easy

**[7:49](https://www.youtube.com/watch?v=83EffKFYeCU&t=469)** plug this in. And if I go back to the first frame, And we get those cool details being added. And uh let's say we want to render this. So how I would uh work to render that is I would very simply just duplicate that.

**[8:21](https://www.youtube.com/watch?v=83EffKFYeCU&t=501)** So first we want to turn our MTM simulation into a density grid. So I can plug this like that. So my output type is the density VDB grid like so. I want to mask this density with the sign distance field. And this sign distance field is coming in from here. So it's premputed. We're grabbing it from the second input as you can see. Second input. Second input. All good. And uh this is already set with a

**[8:51](https://www.youtube.com/watch?v=83EffKFYeCU&t=531)** proper resolution. Now I want to get my debris. So I'm going to do an object merge. Grabbing my debris here. And we're just going to duplicate this node. And even if it's not in MPM sim, we can use uh the MPM surface to surface surface those debris. So I plug this in. So now it's complaining that we are not um so we we don't have the resolution set up. So this resolution that is expected to be coming from the MPM sim is not because this is not an MPM sim.

**[9:22](https://www.youtube.com/watch?v=83EffKFYeCU&t=562)** So we can just override that. And then we're going to steal the resolution from this density grid here in an expression. npm surface one we want to grab the first grid and then intrinsic voxal size and we want the first component. And now if we do this we have a effectively grabbed this resolution

**[9:54](https://www.youtube.com/watch?v=83EffKFYeCU&t=594)** here. After that can just combine both grids with the maximum operation. and then uh yeah I don't want this to be I don't want the the density here to be multiply by a mask SDF so I just disable that so we can see our secondaries this might be a little too opaque for this uh those those fine points so I'm just going to reduce that by half so yeah just a little bit more transparent and

**[10:25](https://www.youtube.com/watch?v=83EffKFYeCU&t=625)** this is what we get in terms of density field for our npm And then we when we combine both together we get this uh added level of details. And this would
