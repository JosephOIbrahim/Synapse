---
title: "MPM H21 Masterclass Overview"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "overview", "houdini_21", "masterclass", "new_features", "mpm_solver"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=nD183jP3H4Y"
  series: "SideFX MPM H21 Masterclass"
  part: 0
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 70
duration_range: "0:55 - 3:25"
---

# MPM H21 Masterclass Overview

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=nD183jP3H4Y)
**Presenter:** Alex Wevinger
**Part:** 0 of 18
**Transcript Lines:** 70

---

## Transcript

**[0:55](https://www.youtube.com/watch?v=nD183jP3H4Y&t=55)** Hello and welcome to this very exciting npm master class for Udini 21. My name is Alex Wevinger and this master class is a followup on the master class that I did for 20.5. And just so you know, this is not an introduction to MPM. So this already assumes that you know how the solver works at the eye level. So in general, how to use it. And here we're just talking about the new features that we introduced as well as the new nodes that we added to streamline the post simulation workflow. So let's take a look at the uh outline of this master

**[1:25](https://www.youtube.com/watch?v=nD183jP3H4Y&t=85)** class. So first thing uh we look at the new features. So we added surface tension to mpm an auto sleep mechanism continuous emission expansion. So seems a little complicated but it's just to allow you to source material on top of existing material and create like internal pressure. uh we added per voxal varying friction and stickiness. So this is very helpful if you want to um have control over uh the friction and stickiness per voxil on your colliders. So this uh skips the act that we used to do in 20.5 where we would duplicate the

**[1:57](https://www.youtube.com/watch?v=nD183jP3H4Y&t=117)** colliders but we're going to see that in more details. We have greatly improved the deforming colliders. Then when we're done with the new features we're jumping into those post simulation nodes. So those nodes are all there to just help you streamline the post simulation workflow. So it helps you with surfacing, with debris emission based on where the material is fracturing. And we have those two nodes at the end that work kind of together. And this helps you replicate rigid body dynamics kind of workflow. Uh so you can use MPM to simulate very stiff material like

**[2:28](https://www.youtube.com/watch?v=nD183jP3H4Y&t=148)** concrete for example. And then at the end of the simulation, you can pick this last state of the MPM sim and use that uh to fracture your original asset. And when you're done with this step, you can just retarget the dynamics of the MPM simulation onto this post fractured asset. So uh this might seems a little bit confusing, but u in practice it's going to make sense when we look at it in Houdini. So uh when we have the basics out of the way, now we jump to practical demo scenes. And these are all the scenes that you saw at the very

**[2:58](https://www.youtube.com/watch?v=nD183jP3H4Y&t=178)** beginning of this presentation. So we're not going to do any of these from scratch because that would be way too long. But uh we're going to go through the setups and I'm going to highlight the important parts so you can see how to use those new feature and nodes in more like practical real world scenarios and hopefully all of the assets and obviously the IP file is going to be available to you. So you can look at all of those example on your own or follow along as I'm uh presenting these. So
