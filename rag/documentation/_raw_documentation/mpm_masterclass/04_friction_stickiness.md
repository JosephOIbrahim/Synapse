---
title: "MPM Friction and Stickiness"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "friction", "stickiness", "material_properties", "collision", "adhesion"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=UYj3sUThg-0"
  series: "SideFX MPM H21 Masterclass"
  part: 4
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 123
duration_range: "0:02 - 5:14"
---

# MPM Friction and Stickiness

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=UYj3sUThg-0)
**Presenter:** Alex Wevinger
**Part:** 4 of 18
**Transcript Lines:** 123

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=UYj3sUThg-0&t=2)** Okay, moving on to varying friction and stickiness. So, here we have this very simple scene. This is going to be a collider and this is going to be a source. And I don't know if you remember from the previous release of MPM, if you wanted to have like some part of this collider to have stronger friction than other parts, you would need to separate this collider into different uh MPM uh collider, right? So again just dropping our MPM

**[0:33](https://www.youtube.com/watch?v=UYj3sUThg-0&t=33)** configure recipe. So what you would do basically is you have this collider here and you say okay I want for example I want this part of the collider to have a different friction. So, I'm I'm poly capping both sides and then okay, this is going to be one of them and this is going to be the other one.

**[1:04](https://www.youtube.com/watch?v=UYj3sUThg-0&t=64)** And then I'm merging these two collider together. This is my source. And now if I change, so let's say make this friction 100 and this friction zero and I play, I get very high friction on both of those sides, but in the middle there's no friction and everything is uh flying through. So that was the old way of doing it. And obviously uh it's not that

**[1:36](https://www.youtube.com/watch?v=UYj3sUThg-0&t=96)** uh great because like right now it's very easy pattern. It's just like AV friction, no friction, AV friction. But sometimes you might want something more intricate and it can add some overhead if you split that into a bunch of different MPM colliders. So now there's a new more a new better way to do this. So if I just delete all of this and we're back with this simple setup. Uh on this collider we have some groups that are already set up for us. So I can visualize this like that. And you can

**[2:08](https://www.youtube.com/watch?v=UYj3sUThg-0&t=128)** see that we have those uh rows that are being highlighted by this group. So what I can do is I'm just going to drop down a point wrangle. And here depending on this group. So this is a primitive group. So if at group A I'm going to set friction very high like that. Else I'm going to set friction very low.

**[2:39](https://www.youtube.com/watch?v=UYj3sUThg-0&t=159)** Okay. And now some Python Python reflexes there. Okay. So I'm going to Okay. The group is already disabled. So now I'm looking at at friction and I am going to um Okay, good. So now we see the primitive attribute friction. And if I pipe that into the MPM collider, you can see that the MPM collider, uh, it has now this checkbox here. So

**[3:12](https://www.youtube.com/watch?v=UYj3sUThg-0&t=192)** under material friction can create VDB from attribute. And if I check that and if I middle click, I can see that we now have a friction grid. And this is going to be driven by uh our attribute that we're passing through. And here I can visualize that. So visualize friction. But here you can see um we have just one value for the whole grid and this is not what we expect. And if you uh over here put your mouse right here it tells you well the message is is clipped for you at the moment but it's basically telling you that it's looking for a friction

**[3:43](https://www.youtube.com/watch?v=UYj3sUThg-0&t=223)** point attribute. And right now what we have is a primitive friction attribute. So internally it's going to promote this friction attribute from primitive down to points. So since this is very uh low res what we can do is just cusp uh those points and uh then when we do the promotion we're still going to retain like this very high friction and very low friction otherwise it's just going to be averaged out to a single value. So let's do that cusp. But yeah in general if you want to avoid

**[4:14](https://www.youtube.com/watch?v=UYj3sUThg-0&t=254)** this just make sure that you have a point attribute from the get- go. But here I just want to show you this workar around. So now I'm casping this point here. If we look at the amount of points. So before the 260 points and now we have over a,000 points. And if we go to our MPM collider now we can see in the visualization that we retain our varying friction. So low friction here, high friction there. And that's pretty much it. So yeah, uh here we're only

**[4:45](https://www.youtube.com/watch?v=UYj3sUThg-0&t=285)** playing with this u adding this friction grid. But just keep in mind that you have the exact same tooling if you want to uh play also with the stickiness. So you can now vary per voxle both the friction and stickiness which is really useful. And now if we play this simulation. Okay. So right now it's uh compiling the open CL kernel. So this happens the first time that you're going to run this. And here we have our varying friction on this collider. Very easy to
