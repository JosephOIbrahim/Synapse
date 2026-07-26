---
title: "MPM Car Rain"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "car", "rain", "water", "environment", "surface_tension", "droplets"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=mKg7OWiBQE4"
  series: "SideFX MPM H21 Masterclass"
  part: 13
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 306
duration_range: "0:06 - 13:02"
---

# MPM Car Rain

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=mKg7OWiBQE4)
**Presenter:** Alex Wevinger
**Part:** 13 of 18
**Transcript Lines:** 306

---

## Transcript

**[0:06](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=6)** Okay, let's now take a look at this car rain scene. So here we have our model and we're generating multiple variation of it. So first one is this car that we're going to render. So I just added some thickness to the windows to have proper refraction. And here I'm generating a watertight version of this to use as a collider. And here you can look into the subnet to see how I have done it. Uh after that we need to uh define where the raindrop are going to hit our car.

**[0:38](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=38)** So for that we isolate like a grid on top of the car and we scatter some points project that back to the car to get our raindrop it areas. After that we build some frame looking at this uh yellow vector here. This is the up vector that is pointing normal to the car. And we are also adding like random normals just to add a little bit of uh rotational variation. And we're only going to copy this. Okay, I'm going to remove this obctor visualization. So I'm

**[1:10](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=70)** just going to copy this ring here like this circle where uh each of the raindrop are going to hit. And from there we want to be basically modeling the splash. Right? So, uh, here we want to have full control over how things are going to splash after the raindrop it hit. So, I'm not going to go through all of these, but it's just basically like, yeah, trying to shape, uh, this splash

**[1:41](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=101)** Here, I'm doing some fusing because I have like too many points overlapping. Uh and after that we just do like a particle a VDB from particle and we are left with this shape for our splash. So each of those raindrop have this little crown splash. Cool. And finally we just transfer the velocity back to this small mesh that we're going to use in our MPM source and we're good. So this is for the impact itself. But what about the raindrop

**[2:12](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=132)** falling from the sky? So here we know that our uh simulation is going to end around frame 150. So, we can just do the this little trick where we start from the it position and we just reverse time and go from frame like let's say 160 because we want a little bit of padding and then we walk the frames backward and then we're going to do a simulation here where I'm just like lifting the raindrops from their it position back to uh where they were emitted from. I'm

**[2:44](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=164)** just doing that in reverse. And wherever they the their like starting position, I just delete them like so. And after that, we flip the time again. Flip the velocity. And we're left with uh this rain simulation where um we have this uh synchronization where when this hit the car, we're going to have this ring splash ready to go and ready to be sourced by our MPM sim. So in fact uh we just have to instance some uh spheres on those raindrops and

**[3:14](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=194)** after that there's nothing more to do. So we're not even going to simulate these with npm. So this is just going to be like a layer of a raindrop falling from the sky and uh with npm we're only going to simulate the splash themselves to save on memory. Okay. So here we have our collider and okay. So let's first just check the mpm simulation itself. It's going to be very simple. Um, there's really nothing fancy about it at

**[3:45](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=225)** all. So, I'm using the water preset here. As you can see, I don't think there's anything changed. I'm doing continuous emission. And if we look at our splashes, it looks like that. So, this is again the low res version. Don't forget that we're you can increase the resolution with the global scale controller. So, those are our little models of Splash. And this is the MPM points that we're going to simulate. And um I don't think there's a lot to talk

**[4:16](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=256)** about here. So, I'm just um killing the points as soon as they hit the ground again to save on memory. Um um obviously, uh surface tension is on here and it's pretty strong. So, that's why I need to increase the minimum amount of substeps to make sure that we don't run into any instability. reducing this material condition again to make this more stable and doubling the amount of dub substeps. Uh after that on the collision tab here I'm enabling particle level collision to get something very precise on tin

**[4:48](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=288)** colliders and I'm also increasing this detection distance. And the only reason why I'm doing this is to make sure that we have this cool uh if you look at the final simulation, you see how the water is trickling down and then collecting on those geometry uh lip. So this is exactly what you want. You want the water to just be uh gathering there in those area and then when there's enough water pouring in that region then it's going to force the water to uh flow over and and pour on the level downstream. So

**[5:19](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=319)** this is exactly what you expect from uh water running onto some geometry like this. And this is why we are increasing this collision detection. If you keep this to one, which is a default, you might have a hard time to get those particle to be sticking to the underside of this geometry. So just a little act that can get you there. Uh and here on the other side, we have like this branch that we haven't really discussed. It's very similar to this the splash branch here, but instead of modeling a splash,

**[5:49](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=349)** we're modeling like a a mist impact, like mist burst. If you look at this, just a bunch of small points that we're going to render as mist, very very small water particulate that are going to burst from those raindrop impacts. And for that, I'm just doing like a pop simulation here. And here you can see the kind of uh visual we get from this layer. So very simple simulation and it's going to be rendered uh as very small droplets just to add this high

**[6:21](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=381)** frequency level of detail. Okay. Then to mesh this MPM simulation. I don't think we're doing anything special here. So this is the result that we have with this Afres. If I look at the MPM surface, we are just using this VDB from particles. it could be a good opportunity to use the neural point surface with the liquid model. Uh but here yeah we're just using this very basic approach. Some dilation, some erosion, some smoothing. These are all

**[6:54](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=414)** uh run in in sequence like that and uh it will give like a pretty decent liquid look for our mesh. Um okay. Yeah, this is an important part here. So after caching we are uh looking at the distance of uh each of those points to the car collider and um we are storing this attribute here this IUR and the reason for that is sometimes uh when you try to render that

**[7:25](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=445)** you're not exactly like in in the real world this part of the water would be perfectly sitting on the car so the light will go from the water to hitting the middle of the car in one like transition if you want but in 2D you can have like some air gaps in between the car and the water and since the index of refraction is like 1.33 something like that you might get a total internal refraction and then the water the the ray of light is not going to go from water to metal but from water to total

**[7:57](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=477)** internal reflection so it's going to stay inside of the water sheet and it might go and sample the HDR so you're going to get like very very bright reflection everywhere um on the car where you have water which is highly unrealistic because you shouldn't have those total internal reflection. So to avoid this you can just uh have an attribute that will keep track of where you are in terms of distance relative to the car. So here I'm just going to display this IUR attribute and everything that is red

**[8:28](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=508)** we're going to keep the normal water IUR of 1.33 but everything that is purple which is very close the car we're going to set the IR to be just one. So no um no like special index of refraction. So if the array of light hits this uh interface, it's just going to go through in straight line and it it won't be uh um uh bent or it won't do any kind of internal refraction. And this is exactly what we want to avoid those um rendering

**[8:59](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=539)** issues. So this is something that we're going to use in the shader. And I can very quickly So here we have our materials, the rain material. And here we're taking this IR material and just remapping it from 0 to 1 to 0 to 1.33. And this is what we are passing in the shader. Okay. After that uh we did another like this is all unnecessary additional layer

**[9:31](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=571)** has nothing to do with MPM but just like to try to make the the shot more complete. We also add some condensation layer. So here I'm just basically scattering a lot of points on the car like what you're seeing here. And all of those little points could be rendered as small droplets. So some condensation on top of the car. And here what I'm doing is a solve where every time there's some water flowing on top of those points, I'm going to reduce their P scale to something very low. And as time goes on

**[10:01](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=601)** without having water flowing on top of it, those droplets are going to get bigger and bigger. Uh so it's going to restore this condens cond condensation back and this is being handled by this uh like little wrangle here. There's nothing complex going on here. And what this allows you to do at the end when we cache this is we have this condensation attribute that we can visualize.

**[10:36](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=636)** And then you can see that those points that are reduh are going to be um like full full pcale. So rendered with their uh complete pcale. And then everything that is purple is going to be either well purple is going to be reduced to zero but in the transition from purple to red the points are going to scale back up to their original Pcale. And this is going to create this nice effects where you have water running over the car. It's going to remove this condensation, but as time goes on the

**[11:07](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=667)** condensation will restore itself. And the last piece of the puzzle, which again has nothing to do with MPM, but it's just fun to add those little details, is uh we're going to create a ground. And I'm just going to show the car in context here. So, we had this ground here. And uh now we want to have some puddles. So, there's the concrete uh ground, which I'm going to color here yellow. And we are adding some static puddles.

**[11:37](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=697)** And in front here where you have a lot of water just collecting and and in fact not collecting but being deleted in front. I'm also going to add this dynamic puddle that we're going to simulate. And uh in the version I showed the this puddle is very like uh isolated in front. So we can see a lot of the points being killed off here on the side of the car. So, I'm just recommending if you redo this scene, um, or if you want to improve on it, this dynamic puddle should probably go all the way back on the side of the car and it would

**[12:11](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=731)** probably give better results. Good. So, uh, now if you want to look at the setup for this dynamic model, it just simply we're extracting a part of the grid. And then all of those points that are right about to be deleted in front of the car, the point that we're seeing here, I'm just going to project that uh on this dynamic puddle grid. And I'm going to displace the grid. So, we can see there are some holes here from this displacement. And after that, I'm just doing a simple ripple solve. And we're

**[12:43](https://www.youtube.com/watch?v=mKg7OWiBQE4&t=763)** left with this kind of simulation which is going to add a little bit of realism um for those points being killed off. And it's um just just a better integration for this shot. And at the end here, I'm simply grabbing 25% of this amplitude from the simulation just to make it less extreme in terms of uh displacement.
