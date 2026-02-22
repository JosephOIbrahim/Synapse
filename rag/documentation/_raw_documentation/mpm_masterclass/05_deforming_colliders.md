---
title: "MPM Deforming Colliders"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "deforming_colliders", "collision", "animated_geometry", "rbd"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=RylqkW5ePww"
  series: "SideFX MPM H21 Masterclass"
  part: 5
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 203
duration_range: "0:02 - 8:57"
---

# MPM Deforming Colliders

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=RylqkW5ePww)
**Presenter:** Alex Wevinger
**Part:** 5 of 18
**Transcript Lines:** 203

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=RylqkW5ePww&t=2)** So the last new feature I want to cover is those improved deforming colliders. So let's pick like a very very basic example. Okay. So we have this box. This is going to be like our source. And we have this sphere. And the sphere is going down on the source and going back up. And believe it or not, this used to not work with deforming collider. So, I don't know if you've tried something like that in the H20.5, but let's just uh drop our

**[0:34](https://www.youtube.com/watch?v=RylqkW5ePww&t=34)** favorite recipe, the MPM configure. And I'm just going to go back the first frame. Uh so, this is our source. This is our collider. The collider is going to be uh no, in this case, the collider is going to be um yeah, deforming. And then I just want to show you. So if you tried this before, uh so right now I have sticky set to zero. Okay, but let's uh assume that this is set to one. Okay, so normally if you play this and I'm going

**[1:08](https://www.youtube.com/watch?v=RylqkW5ePww&t=68)** to remove the template flag here. So if you play that with the previous version of Udini, this would not stick at all. So even if you have sticky set to one, it would give you something similar to that. But now this has been fixed there. There's been many improvement to those deforming colliders. So if you play something like that with a deforming collider, you're going to get the expected result of having the material stick to the collider, which is great. Now, let's pick like a most uh a more

**[1:39](https://www.youtube.com/watch?v=RylqkW5ePww&t=99)** relevant example, something that um you might be um having to do in production sometimes. So we have our crag animation with the hammer swinging in the air like that at a pretty fast velocity. So, especially in those frame here and uh maybe you want some material to be uh sticking to the hammer and then to continue sticking sticking sticking all the way back to this pose and you still want some material to be in here. I don't know if you've tried something like that in the past with the previous

**[2:09](https://www.youtube.com/watch?v=RylqkW5ePww&t=129)** version of npm, but this used to be pretty uh hard to achieve. So, again, let's just drop down our npm configure recipe. So this is our source with snow and [snorts] this is our collider and again we're going to pick animated So there's been this uh checkbox that was added extend to cover velocity. Let's just uncheck that just to revert to something closer to what we had in

**[2:41](https://www.youtube.com/watch?v=RylqkW5ePww&t=161)** the previous version of npm. So now if we increase our resolution Now if I play this. Oh, and uh I'm going to add some I'm going to add a lot of stickiness and friction. Okay. So let's say 100 in both. So just the maximum because we want to give us as much chance as possible to have some materialing to this hammer throughout the whole shot. So if I play this, you are going to see that some of the

**[3:13](https://www.youtube.com/watch?v=RylqkW5ePww&t=193)** material is going to stick to the hammer. So this is fine. And uh some of this material is also going to be thrown away with with this uh motion that Craig is doing. So this is this is looking good. But right at this point, you can see that we have lost everything. So if I just like display the points, all of the material that was hanging to the hammer has detached. So it's still going to give us some cool interaction but we are not able to uh keep some of this material stuck to the average. So then

**[3:44](https://www.youtube.com/watch?v=RylqkW5ePww&t=224)** what do you do? Do you start like acting away with animating points and emitting those bits of material as the the frame range is evolving like as some kind of continuous emission. You you could do that but it's not as cool as just being able to get proper stickiness on the collider. Right. So now we can just enable this expand to cover velocity checkbox and let's look at the result that we're getting.

**[4:17](https://www.youtube.com/watch?v=RylqkW5ePww&t=257)** So this is now the default that you will So it seems similar but as you can see a lot more material is now sticking to the hammer. still sticking. We still have something. And even like the the hammer is now rotating and we still have some stuff

**[4:50](https://www.youtube.com/watch?v=RylqkW5ePww&t=290)** I'm just going to move the camera a little bit so we can see better what's happening. So, see, like maybe I'm going to go to frame 50 just to be really like done with this uh fast motion. And as you can tell, we have this really nice uh trail of material that was thrown on the ground. And we still have some material that is hanging uh to the hammer and also some of it that is falling right before it's going to continue it its motion forward. So,

**[5:21](https://www.youtube.com/watch?v=RylqkW5ePww&t=321)** that's pretty cool. And the reason why uh this is not working is well there was many changes to how deforming colliders are being computed. But the main thing is very simple. If you just look at the collider itself and not the simulation, you can tell that here when we have like very fast motion like this, you can tell that the uh bounding box is uh a lot further from the hammer compared to uh the previous version. So if I just disable this expand to cover velocity, it used to be very tight around the

**[5:53](https://www.youtube.com/watch?v=RylqkW5ePww&t=353)** collider. So let me go to the drawing board and explain to you like the difference. So let's say this is a frame with the collider and this is like the previous frame of the same collider and we have bounding box like very tightly bounding our SDF in velocity. So

**[6:25](https://www.youtube.com/watch?v=RylqkW5ePww&t=385)** if you are let's say like this is a frame zero for example and this is frame one and it's going in that direction. So if you're perfectly on frame zero and you sample here ear here ear here no problem. You always have valid velocity and valid sign distance information because you're within the activated region of this VDB. Same thing for if you're on frame one and you sample here here. um given that all of these all of

**[6:55](https://www.youtube.com/watch?v=RylqkW5ePww&t=415)** this empty space is also filled with like active voxels and tiles you're going to get proper information but what happens if you're sampling in between two frames so it's you're sampling because you know npm has a lot of substeps right so we're very often sampling outside of those integer frames so if you're sampling at 0.5 in between those two frames uh and you're sampling here let's say or like it could be it could be uh other places and would still be a problem. But like let's say this is the worst case because we're outside of this uh VDB and

**[7:27](https://www.youtube.com/watch?v=RylqkW5ePww&t=447)** we're outside of this VDB. So if I'm trying to interpolate the sign distance information, I have garbage in in both VDBs because [clears throat] there's no data. And also if I'm I'm trying to sample velocity for both of these VDBs, I'm also sampling garbage in the on both sides. Like if I'm sampling here, uh maybe I'm going to get some valid data from this VDB, but nothing from this one. And same thing here like I'm just going to get valid data from from this guy and not this guy. So what you need to do is just to have like a

**[7:58](https://www.youtube.com/watch?v=RylqkW5ePww&t=478)** dilated uh activation region that is based on the velocity that is happening in your animation and you're going to get meaningful uh interpolation. So in this case just to visualize that um so this would be our like dilated binding box for this guy and this would be our dilated bonding box for this guy and let's assume that both of these bonding bugs are fully activated and then this guy is in both this activated

**[8:28](https://www.youtube.com/watch?v=RylqkW5ePww&t=508)** region and this activated region. So now I'm sampling SDF uh and velocity for both of these colliders. I'm getting proper values that make sense and then I'm I'm able to compute the interpolation properly and this is why uh I can have those bits of uh material hanging to the collider from frame zero to frame one because I always know where this collider here uh is in space in between integer frames and I also have meaningful um velocity information.
