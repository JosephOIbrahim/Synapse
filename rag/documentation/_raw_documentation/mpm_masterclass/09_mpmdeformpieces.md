---
title: "MPM Deform Pieces"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "mpmdeformpieces", "deformation", "pieces", "chunks", "post_simulation"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=iasTN8SZC4A"
  series: "SideFX MPM H21 Masterclass"
  part: 9
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 124
duration_range: "0:02 - 5:10"
---

# MPM Deform Pieces

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=iasTN8SZC4A)
**Presenter:** Alex Wevinger
**Part:** 9 of 18
**Transcript Lines:** 124

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=iasTN8SZC4A&t=2)** Okay, let's now take a look at the npm Oops. Okay, so first thing it needs is the output of this node and then the mpm sim. And voila, we have something that is being now retargeted and it's being animated following the simulation that we had. So this is the simulation that we have and now we can switch to this

**[0:32](https://www.youtube.com/watch?v=iasTN8SZC4A&t=32)** and we have those fractured pieces following on this dynamics. Perfect. In terms of parer you have a start frame and an end frame. The reason that both are grayed out is because uh the first frame is coming from this ear from the mpm solver and the end frame has been defined here on this node as you might remember. So you can override them if you want, but they are all flowing to this node automatically. After that, the most important thing to look at is this retargeting type. So if we get a little

**[1:04](https://www.youtube.com/watch?v=iasTN8SZC4A&t=64)** bit closer to this impact frame, uh we're currently doing point and piece. So it means that it's using two different algorithm to do the retargeting. So first one being used is this uh piece uh algorithm which is just a basic transform. So each uh fracture pieces is looking at the closest NPM point and it's stealing the transformation m matrix from this point and applying it to each piece. So as you can tell when the material is just slightly deforming it introduces a lot of cracks which is not really something that we want as opposed to this way of

**[1:34](https://www.youtube.com/watch?v=iasTN8SZC4A&t=94)** working we have this other method point base which is going to not care about pieces at all. So each point of this geometry is just looking at the closest MPM point and um yeah these points are being transformed based on on their closest MPM particle. So obviously this introduce a lot of stretching. So to get the best of both worlds so no cracks here and no stretching there we are transferring from one method to the other based on how the pieces are being stretched. So here if we go back to this

**[2:07](https://www.youtube.com/watch?v=iasTN8SZC4A&t=127)** first method you have this stretch ratio and this is basically telling you so where what is the amount of stretching where uh past that point looking at this mode so where I have more where I have too much stretching from that mode at what point I'm going to switch back to this mode and this is exactly what's happening so this is the the number that you're defining that will make you switch per piece from this mode to this mode. And in the end, when this is

**[2:37](https://www.youtube.com/watch?v=iasTN8SZC4A&t=157)** dialed properly, you get the both the best of both world where you have like those very clean uh geometry here, those uh very like sharp pieces, but where it's just like deforming a little bit. You don't have those cracks that we have with this method. After that, we have this closed gaps. Uh I'm not going to talk about that right now because I have a better example with metal tearing to show you this. And finally, you just have those attribute transfer where if you want like if you have extra data coming here that you

**[3:07](https://www.youtube.com/watch?v=iasTN8SZC4A&t=187)** want to transfer over this fractured geometry, this can be done right here. Okay. Uh and the last thing I want to show you is that you're not forced to use this node. If you want to just like move pieces with an MPM simulation, you don't have to go through this MPM fracture node. So, just as an example, I'm going to use a fuse there to decimate a little bit. Oops. To decimate a little bit the the point cloud that we have on the first frame and then

**[3:38](https://www.youtube.com/watch?v=iasTN8SZC4A&t=218)** copy to points box. Going to put some color so we can visualize that better. Maybe a little more contrast. My god. Okay. Like that. Good. H. And then I'm just going to frame old because we only have points on the first frame in this case. Now we can just Oh yeah, I

**[4:10](https://www.youtube.com/watch?v=iasTN8SZC4A&t=250)** need also to add this name attribute that I was talking about. So this is adding this name. It's going to be important. And now we can pass that to this node. So now it's complaining that we need this end frame because this is no longer being passed from this stream. So I can just go to manual mode, enable this, set that back to 50. And now we should be all good. And we are. So now if I play this, you can see that our points are

**[4:41](https://www.youtube.com/watch?v=iasTN8SZC4A&t=281)** now being transformed using the MPM simulation. Looking very good. So this is definitely useful if you want to instance some geometry either on the MPM points or like nearby. So you just have a distribution of pieces that you want to be captured with this MPM sim and be deformed around. This is definitely like a a good way of doing that. And yeah, in the end it's just to show you that you're not always forced to fracture the original asset. You can just create new geometry and
