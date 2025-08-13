import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  query,
  setDoc,
  where
} from "firebase/firestore"
import { firestore } from "../firebase"

export type Results = { [key: string]: string[] }

function setSubscriptionRef(uid: string | undefined) {
  return collection(firestore, `/users/${uid}/activeTopicSubscriptions/`)
}

export async function FollowingQuery(uid: string | undefined) {
  let results: Results = {
    bills: [],
    orgs: []
  }

  const subscriptionRef = setSubscriptionRef(uid)

  const q1 = query(
    subscriptionRef,
    where("uid", "==", `${uid}`),
    where("type", "==", `bill`)
  )
  const querySnapshotBills = await getDocs(q1)
  querySnapshotBills.forEach(doc => {
    // doc.data() is never undefined for query doc snapshots
    doc.data().billLookup ? results.bills.push(doc.data().billLookup) : null
  })

  const q2 = query(
    subscriptionRef,
    where("uid", "==", `${uid}`),
    where("type", "==", `org`)
  )
  const querySnapshotOrgs = await getDocs(q2)
  querySnapshotOrgs.forEach(doc => {
    // doc.data() is never undefined for query doc snapshots
    doc.data().userLookup ? results.orgs.push(doc.data().userLookup) : null
  })

  return results
}

type FollowableTopics = "bill" | "testimony"
interface IFollowTopicData<TopicType extends FollowableTopics, TopicData> {
  uid?: string
  topicName: string
  type: TopicType
  data: TopicData
}
type FollowProfileData = IFollowTopicData<
  "testimony",
  { userLookup: { profileId: string } }
>
type FollowBillData = IFollowTopicData<
  "bill",
  { billLookup: { billId: string; court: number } }
>
type FollowTopicData = FollowBillData | FollowProfileData

export const followTopic = async ({ data, ...props }: FollowTopicData) => {
  const subscriptionRef = setSubscriptionRef(props.uid)
  await setDoc(doc(subscriptionRef, props.topicName), { ...props, ...data })
}

export async function unfollowTopic(
  uid: string | undefined,
  topicName: string
) {
  const subscriptionRef = setSubscriptionRef(uid)

  await deleteDoc(doc(subscriptionRef, topicName))
}

export async function TopicQuery(uid: string | undefined, topicName: string) {
  let result = ""

  const subscriptionRef = setSubscriptionRef(uid)

  const q = query(subscriptionRef, where("topicName", "==", topicName))
  const querySnapshot = await getDocs(q)
  querySnapshot.forEach(doc => {
    // doc.data() is never undefined for query doc snapshots
    result = doc.data().topicName
  })
  return result
}
